"""
小売メダリオンアーキテクチャ Gold layer 集計・保存スクリプト（Databricks Free Edition想定）
==================================================================

■ 今回のスコープ
    Silver layerで品質改善済みのデータを集計し、既に表定義（空表）として
    作成済みのGold layer 4表にデータを保存する。
    （表のスキーマ・NOT NULL制約は build_retail_gold_layer_tables.py で
      CREATE TABLE 済みのため、本スクリプトは集計結果を書き込むのみ）

■ Silver layerでの下準備（本スクリプトが前提とするもの）
    ・重複transactionは除去済み（1取引1行）
    ・is_store_registered / is_product_registered フラグでマスター整合性を判定済み
    ・discount null は0円補完済み、sales_amountは再計算済み
    ・transaction_timestamp / transaction_date で取引日時が正規化済み
      （解析不能な場合のみnull）

■ 集計方針（Gold layer 4表）
    1. gold_daily_store_sales         … store/product双方が登録済みかつ
                                          transaction_dateが解析できた取引のみを
                                          日付×店舗で集計
    2. gold_category_sales            … store/product双方が登録済みの取引を
                                          商品カテゴリで集計
    3. gold_store_ranking              … store/product双方が登録済みの取引を
                                          店舗で集計し、売上金額で順位付け
    4. gold_unregistered_master_report … store_idまたはproduct_idが未登録の
                                          取引をそのまま抽出（集計はしない）

■ パフォーマンス最適化の方針
    ・有効データ（store/product双方が登録済み）は1,2,3の集計すべてで再利用するため、
      商品カテゴリのjoinまで済ませた状態で1回だけ作成しcache()する
      （3回それぞれが個別にsilver_pos_salesを読み直す／filterし直すのを避ける）
    ・store_master・product_masterのような小さいマスター表は broadcast() で
      明示的にブロードキャスト結合し、事実表（silver_pos_sales由来）側の
      シャッフルを発生させないようにする
    ・使い終えたキャッシュは最後にunpersist()して明示的に解放する

Databricks ノートブックでは spark はクラスターから自動注入されるため
SparkSession.builder は呼ばない。
"""

from pyspark.sql import functions as F
from pyspark.sql.window import Window


# ──────────────────────────────────────────────
# 0. 依存データの存在確認・自動生成
#    ※ Python変数ではなく永続化されたDeltaテーブルの有無で判定することで、
#      ノートブック／セッションが分かれていても正しく動作するようにする
# ──────────────────────────────────────────────

if not spark.catalog.tableExists("silver.silver_pos_sales"):
    print("silverスキーマのテーブルが存在しないため、Silver layerの構築を先に実行します。")
    with open("build_retail_silver_layer_tables.py", encoding="utf-8") as f:
        exec(f.read(), globals())

if not spark.catalog.tableExists("gold.gold_daily_store_sales"):
    print("goldスキーマの表定義が存在しないため、Gold layerの表定義（空表）を先に作成します。")
    with open("build_retail_gold_layer_tables.py", encoding="utf-8") as f:
        exec(f.read(), globals())


# ================================================================
# Output 1: Silver layerのデータを集計しGold layerの表に保存するコード
# ================================================================

df_silver_pos = spark.table("silver.silver_pos_sales")
df_silver_stores = spark.table("silver.silver_store_master")
df_silver_products = spark.table("silver.silver_product_master")

# store/product双方がマスター登録済みの取引のみを集計対象とする。
# 1・2・3の集計すべてで使い回すため、商品カテゴリのjoinまでこの時点で済ませてcache()する
# （集計ごとにsilver_pos_salesを読み直す／filterし直すコストを1回にまとめる）。
# product_masterは極small（十数件程度）なのでbroadcastし、事実表側のシャッフルを避ける。
df_valid_pos = (
    df_silver_pos
    .filter(F.col("is_store_registered") & F.col("is_product_registered"))
    .join(
        F.broadcast(df_silver_products.select("product_id", "category")),
        on="product_id", how="inner",
    )
    .cache()
)
# マスター未登録の取引（gold_unregistered_master_report向け）。こちらも件数確認で再利用するためcache()する
df_invalid_pos = df_silver_pos.filter(
    ~F.col("is_store_registered") | ~F.col("is_product_registered")
).cache()


# ──────────────────────────────────────────────
# 1. gold_daily_store_sales（日別店舗別売上）
# ──────────────────────────────────────────────

df_gold_daily_store_sales = (
    df_valid_pos
    .filter(F.col("transaction_date").isNotNull())
    .groupBy("transaction_date", "store_id")
    .agg(
        F.count("transaction_id").alias("transaction_count"),
        F.sum("quantity").alias("total_quantity"),
        F.sum("sales_amount").alias("total_sales_amount"),
    )
    .join(
        F.broadcast(df_silver_stores.select("store_id", "store_name", "region")),
        on="store_id", how="inner",
    )
    .select(
        F.col("transaction_date").alias("sales_date"),
        "store_id", "store_name", "region",
        "transaction_count", "total_quantity", "total_sales_amount",
    )
)

(
    df_gold_daily_store_sales.write
    .format("delta")
    .mode("overwrite")
    .saveAsTable("gold.gold_daily_store_sales")
)
print("gold_daily_store_sales 集計・保存完了")


# ──────────────────────────────────────────────
# 2. gold_category_sales（商品カテゴリ別売上）
# ──────────────────────────────────────────────

df_product_count_by_category = (
    df_silver_products.groupBy("category").agg(F.count("product_id").alias("product_count"))
)

# df_valid_posは既にproduct_masterとjoin済み（category列を保持）のため、再joinは不要
df_gold_category_sales = (
    df_valid_pos
    .groupBy("category")
    .agg(
        F.count("transaction_id").alias("transaction_count"),
        F.sum("quantity").alias("total_quantity"),
        F.sum("sales_amount").alias("total_sales_amount"),
    )
    .join(F.broadcast(df_product_count_by_category), on="category", how="inner")
    .select("category", "product_count", "transaction_count", "total_quantity", "total_sales_amount")
)

(
    df_gold_category_sales.write
    .format("delta")
    .mode("overwrite")
    .saveAsTable("gold.gold_category_sales")
)
print("gold_category_sales 集計・保存完了")


# ──────────────────────────────────────────────
# 3. gold_store_ranking（店舗ランキング）
# ──────────────────────────────────────────────

df_store_agg = (
    df_valid_pos
    .groupBy("store_id")
    .agg(
        F.count("transaction_id").alias("transaction_count"),
        F.sum("quantity").alias("total_quantity"),
        F.sum("sales_amount").alias("total_sales_amount"),
    )
)

ranking_window = Window.orderBy(F.col("total_sales_amount").desc())

df_gold_store_ranking = (
    df_store_agg
    .withColumn("sales_rank", F.rank().over(ranking_window).cast("int"))
    .join(
        F.broadcast(df_silver_stores.select("store_id", "store_name", "region", "store_type")),
        on="store_id", how="inner",
    )
    .select("sales_rank", "store_id", "store_name", "region", "store_type",
            "total_sales_amount", "total_quantity", "transaction_count")
    .orderBy("sales_rank")
)

(
    df_gold_store_ranking.write
    .format("delta")
    .mode("overwrite")
    .saveAsTable("gold.gold_store_ranking")
)
print("gold_store_ranking 集計・保存完了")


# ──────────────────────────────────────────────
# 4. gold_unregistered_master_report（マスター未登録レポート）
#    ※ 集計は行わず、未登録取引をそのまま抽出する
# ──────────────────────────────────────────────

df_gold_unregistered_master_report = (
    df_invalid_pos
    .withColumn(
        "issue_type",
        F.when(~F.col("is_store_registered") & ~F.col("is_product_registered"),
               F.lit("store_id未登録,product_id未登録"))
         .when(~F.col("is_store_registered"), F.lit("store_id未登録"))
         .otherwise(F.lit("product_id未登録"))
    )
    .select(
        "transaction_id", "issue_type", "store_id", "is_store_registered",
        "product_id", "is_product_registered", "customer_id",
        F.col("transaction_datetime_raw").alias("transaction_datetime"),
        "quantity", "unit_price", "discount_amount", "sales_amount",
    )
)

(
    df_gold_unregistered_master_report.write
    .format("delta")
    .mode("overwrite")
    .saveAsTable("gold.gold_unregistered_master_report")
)
print("gold_unregistered_master_report 集計・保存完了")


# ================================================================
# Output 2: Gold layerとして保存した表のデータ・件数を表示するコード
# ================================================================

GOLD_TABLES = [
    "gold_daily_store_sales",
    "gold_category_sales",
    "gold_store_ranking",
    "gold_unregistered_master_report",
]

print("\n" + "=" * 80)
print("=== Gold layer 各表のデータ（先頭5件） ===")
print("=" * 80)

print("\n--- gold.gold_daily_store_sales ---")
spark.table("gold.gold_daily_store_sales").orderBy("sales_date", "store_id").show(5, truncate=False)

print("\n--- gold.gold_category_sales ---")
spark.table("gold.gold_category_sales").orderBy(F.col("total_sales_amount").desc()).show(5, truncate=False)

print("\n--- gold.gold_store_ranking ---")
spark.table("gold.gold_store_ranking").orderBy("sales_rank").show(5, truncate=False)

print("\n--- gold.gold_unregistered_master_report ---")
spark.table("gold.gold_unregistered_master_report").show(5, truncate=False)

print("\n" + "=" * 80)
print("=== Gold layer 各表の件数 ===")
print("=" * 80)
for table_name in GOLD_TABLES:
    full_name = f"gold.{table_name}"
    count = spark.table(full_name).count()
    print(f"  {full_name:<32} : {count:>4,} 件")


# ================================================================
# Output 3: Gold layerの設計に基づいて集計ができているかチェックするコード
# ================================================================

print("\n" + "=" * 80)
print("=== 集計結果の整合性チェック ===")
print("=" * 80)

df_gold_daily = spark.table("gold.gold_daily_store_sales")
df_gold_category = spark.table("gold.gold_category_sales")
df_gold_ranking = spark.table("gold.gold_store_ranking")
df_gold_unregistered = spark.table("gold.gold_unregistered_master_report")

valid_count = df_valid_pos.count()
invalid_count = df_invalid_pos.count()

# [1] gold_daily_store_sales: transaction_count合計は「有効データ」件数以下（解析不能日付は対象外）
daily_txn_total = df_gold_daily.agg(F.sum("transaction_count")).first()[0] or 0
unparseable_in_valid = df_valid_pos.filter(F.col("transaction_date").isNull()).count()
print(f"[1] gold_daily_store_sales: transaction_count合計 {daily_txn_total} 件 + "
      f"日付解析不能で対象外 {unparseable_in_valid} 件 = {daily_txn_total + unparseable_in_valid} 件"
      f"（有効データ件数 {valid_count} 件と一致すべき）"
      f" -> {'OK' if daily_txn_total + unparseable_in_valid == valid_count else 'NG'}")

# [2] gold_category_sales と gold_store_ranking の売上合計が一致するか（同じ有効データの別軸集計）
category_total_sales = df_gold_category.agg(F.sum("total_sales_amount")).first()[0] or 0
ranking_total_sales = df_gold_ranking.agg(F.sum("total_sales_amount")).first()[0] or 0
print(f"[2] gold_category_sales売上合計 {category_total_sales:,.0f} 円 == "
      f"gold_store_ranking売上合計 {ranking_total_sales:,.0f} 円 "
      f"-> {'OK' if abs(category_total_sales - ranking_total_sales) < 0.01 else 'NG'}")

# [3] gold_category_sales / gold_store_ranking のtransaction_count合計が有効データ件数と一致するか
category_txn_total = df_gold_category.agg(F.sum("transaction_count")).first()[0] or 0
ranking_txn_total = df_gold_ranking.agg(F.sum("transaction_count")).first()[0] or 0
print(f"[3] gold_category_sales取引件数合計 {category_txn_total} 件 / "
      f"gold_store_ranking取引件数合計 {ranking_txn_total} 件 / "
      f"有効データ件数 {valid_count} 件 "
      f"-> {'OK' if category_txn_total == ranking_txn_total == valid_count else 'NG'}")

# [4] gold_category_sales.product_count合計 == silver_product_master全件数
product_count_total = df_gold_category.agg(F.sum("product_count")).first()[0] or 0
master_product_count = df_silver_products.count()
print(f"[4] gold_category_sales.product_count合計 {product_count_total} == "
      f"silver_product_master件数 {master_product_count} "
      f"-> {'OK' if product_count_total == master_product_count else 'NG'}")

# [5] gold_store_ranking.sales_rank が 1..店舗数 の連番になっているか
store_count = df_silver_stores.count()
ranking_rows = df_gold_ranking.count()
distinct_ranks = df_gold_ranking.select("sales_rank").distinct().count()
print(f"[5] gold_store_ranking行数 {ranking_rows} == 店舗マスター件数 {store_count}、"
      f"sales_rankの一意な値の数 {distinct_ranks} "
      f"-> {'OK' if ranking_rows == store_count == distinct_ranks else 'NG'}")

# [6] gold_unregistered_master_report件数 == silverでのマスター未登録件数（Knowledge base: 5+5=10件）
print(f"[6] gold_unregistered_master_report件数 {df_gold_unregistered.count()} == "
      f"silverでのマスター未登録件数 {invalid_count}"
      f"（Knowledge base想定: product_id未登録5件 + store_id未登録5件 = 10件） "
      f"-> {'OK' if df_gold_unregistered.count() == invalid_count == 10 else 'NG'}")

# [7] gold_unregistered_master_reportの内訳（issue_type別件数）
print("\n[7] gold_unregistered_master_report issue_type別内訳:")
df_gold_unregistered.groupBy("issue_type").count().show(truncate=False)

# キャッシュした中間データを明示的に解放する
df_valid_pos.unpersist()
df_invalid_pos.unpersist()

print("\n=== Gold layer 集計・保存・整合性チェック完了 ===")
