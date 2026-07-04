"""
小売メダリオンアーキテクチャ Silver layer 構築スクリプト（Databricks Free Edition想定）
==================================================================

■ Silver layerの目的
    Bronze layerの生データに含まれる品質課題を改善し、Gold layerでの集計に
    そのまま使える「整合性のとれた」表として保存する。
    Bronze layerは監査・障害リカバリ用に生データを保持したままにするため、
    本スクリプトはBronzeテーブルを一切変更せず、読み込んでSilverに書き出すのみ。

■ 対応する品質課題（sample/bronze layerに含まれる5種類）と改善方針
    1. 重複transaction     … transaction_id単位でdropDuplicates（1取引1行に正規化）
    2. product_id未登録    … 削除はせず is_product_registered フラグを付与
                              （Gold layerのgold_unregistered_master_reportで利用するため）
    3. store_id未登録      … 削除はせず is_store_registered フラグを付与（同上）
    4. discount null        … coalesce(discount_amount, 0.0) で0円として補完し、
                              sales_amountも quantity×unit_price－discount_amount で再計算
    5. 時刻形式不一致       … 複数フォーマットを順に試すtry_to_timestampで
                              transaction_timestamp（TIMESTAMP）/ transaction_date（DATE）に正規化
                              （解析不能な場合はnullのまま保持し、除去はしない）

■ 前提（Bronze layer）
    bronze.bronze_store_master / bronze.bronze_product_master /
    bronze.bronze_customer_master / bronze.bronze_pos_sales が
    Delta テーブルとして保存済みであること。存在しない場合は本スクリプトが
    build_retail_bronze_layer_tables.py を自動実行して補完する。

Databricks ノートブックでは spark はクラスターから自動注入されるため
SparkSession.builder は呼ばない。
"""

from pyspark.sql import functions as F


# ──────────────────────────────────────────────
# 0. 依存データ（bronzeスキーマの4表）の存在確認・自動生成
#    ※ Python変数ではなく永続化されたDeltaテーブルの有無で判定することで、
#      ノートブック／セッションが分かれていても正しく動作するようにする
# ──────────────────────────────────────────────

if not spark.catalog.tableExists("bronze.bronze_pos_sales"):
    print("bronzeスキーマのテーブルが存在しないため、Bronze layerの構築を先に実行します。")
    with open("build_retail_bronze_layer_tables.py", encoding="utf-8") as f:
        exec(f.read(), globals())


# ================================================================
# Output 1: Bronze layerのデータを品質改善しSilver layerとして保存するコード
# ================================================================

spark.sql("CREATE DATABASE IF NOT EXISTS silver")
spark.sql("USE silver")
print("データベース 'silver' を選択しました")


# ──────────────────────────────────────────────
# 1. 店舗マスター → silver.silver_store_master
#    （品質課題なしのマスターのため、主キー単位の念のためのdedupのみ）
# ──────────────────────────────────────────────

df_silver_store_master = (
    spark.table("bronze.bronze_store_master")
    .dropDuplicates(["store_id"])
    .drop("source_system", "ingested_at")
)
(
    df_silver_store_master.write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("silver.silver_store_master")
)
print("silver_store_master 保存完了")


# ──────────────────────────────────────────────
# 2. 商品マスター → silver.silver_product_master
# ──────────────────────────────────────────────

df_silver_product_master = (
    spark.table("bronze.bronze_product_master")
    .dropDuplicates(["product_id"])
    .drop("source_system", "ingested_at")
)
(
    df_silver_product_master.write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("silver.silver_product_master")
)
print("silver_product_master 保存完了")


# ──────────────────────────────────────────────
# 3. 顧客/会員データ → silver.silver_customer_master
# ──────────────────────────────────────────────

df_silver_customer_master = (
    spark.table("bronze.bronze_customer_master")
    .dropDuplicates(["customer_id"])
    .drop("source_system", "ingested_at")
)
(
    df_silver_customer_master.write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("silver.silver_customer_master")
)
print("silver_customer_master 保存完了")


# ──────────────────────────────────────────────
# 4. POS売上イベント → silver.silver_pos_sales（本丸のクレンジング処理）
# ──────────────────────────────────────────────

# --- 品質課題1: 重複transactionの解消（transaction_id単位でdrop duplicates） ---
df_pos_dedup = spark.table("bronze.bronze_pos_sales").dropDuplicates(["transaction_id"])

# --- 品質課題2・3: マスター未登録の判定フラグを付与（削除せず、Gold layerでの判断材料として残す） ---
valid_store_ids = [r.store_id for r in df_silver_store_master.select("store_id").collect()]
valid_product_ids = [r.product_id for r in df_silver_product_master.select("product_id").collect()]

df_pos_flagged = (
    df_pos_dedup
    .withColumn("is_store_registered", F.col("store_id").isin(valid_store_ids))
    .withColumn("is_product_registered", F.col("product_id").isin(valid_product_ids))
)

# --- 品質課題5: 取引日時の複数フォーマットを解析し、標準化されたTIMESTAMP/DATE列を作成 ---
DATETIME_FORMATS = [
    "yyyy-MM-dd HH:mm:ss",        # 標準フォーマット
    "yyyy/MM/dd HH:mm",
    "dd-MM-yyyy HH:mm:ss",
    "yyyyMMddHHmmss",
    "yyyy-MM-dd'T'HH:mm:ss'Z'",
    "MMM d, yyyy hh:mm a",
    "yyyy.MM.dd HH:mm",
    "d/M/yyyy HH:mm",
    "yyyy-MM-dd HH'時'mm'分'",
    "yyyyMMdd",
]


def parse_multi_format_timestamp(colname: str, formats: list):
    """複数の日時フォーマットを順に試し、最初に解析できた結果を採用する。
    Databricksは既定でANSI SQLモードが有効なため、to_timestampはフォーマット
    不一致時に例外を送出してしまう。try_to_timestampを使うことで、解析に
    失敗した場合は例外にせずnullを返すようにする（解析不能なものは除去せずnullのまま残す）。
    """
    return F.coalesce(*[F.try_to_timestamp(F.col(colname), F.lit(fmt)) for fmt in formats])


# --- 品質課題4: discount null を0円として補完し、sales_amountを再計算 ---
df_silver_pos_sales = (
    df_pos_flagged
    .withColumnRenamed("transaction_datetime", "transaction_datetime_raw")
    .withColumn(
        "transaction_timestamp",
        parse_multi_format_timestamp("transaction_datetime_raw", DATETIME_FORMATS),
    )
    .withColumn("transaction_date", F.to_date(F.col("transaction_timestamp")))
    .withColumn("discount_amount", F.coalesce(F.col("discount_amount"), F.lit(0.0)))
    .withColumn(
        "sales_amount",
        F.col("quantity") * F.col("unit_price") - F.col("discount_amount"),
    )
    .select(
        "transaction_id",
        "store_id", "is_store_registered",
        "product_id", "is_product_registered",
        "customer_id",
        "transaction_datetime_raw", "transaction_timestamp", "transaction_date",
        "quantity", "unit_price", "discount_amount", "sales_amount",
    )
)

(
    df_silver_pos_sales.write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("silver.silver_pos_sales")
)
print("silver_pos_sales 保存完了")


# ================================================================
# Output 2: Silver layerとして保存した表のデータ・件数を表示するコード
# ================================================================

SILVER_TABLES = [
    "silver_store_master",
    "silver_product_master",
    "silver_customer_master",
    "silver_pos_sales",
]

print("\n" + "=" * 80)
print("=== Silver layer 各表のデータ（先頭5件） ===")
print("=" * 80)

for table_name in SILVER_TABLES:
    full_name = f"silver.{table_name}"
    print(f"\n--- {full_name} ---")
    spark.table(full_name).show(5, truncate=False)

print("\n" + "=" * 80)
print("=== Silver layer 各表の件数 ===")
print("=" * 80)

for table_name in SILVER_TABLES:
    full_name = f"silver.{table_name}"
    count = spark.table(full_name).count()
    print(f"  {full_name:<28} : {count:>4,} 件")


# ================================================================
# Output 3: 品質改善後の品質チェック（Bronze→Silverでどう改善されたか）
# ================================================================

print("\n" + "=" * 80)
print("=== 品質チェック: Bronze → Silver でのクレンジング結果 ===")
print("=" * 80)

df_bronze_pos = spark.table("bronze.bronze_pos_sales")
df_silver_pos = spark.table("silver.silver_pos_sales")

# 1. 重複transaction
bronze_dup_rows = (
    df_bronze_pos.groupBy("transaction_id").count().filter(F.col("count") > 1)
    .agg(F.sum("count")).first()[0] or 0
)
silver_dup_groups = df_silver_pos.groupBy("transaction_id").count().filter(F.col("count") > 1).count()
print(f"[1] 重複transaction     : Bronze {bronze_dup_rows:>3} 件が重複 → "
      f"Silverでの重複transaction_idグループ数 {silver_dup_groups}（0件が正しい）")

# 2. product_id未登録（削除ではなくフラグ化されていることを確認）
unregistered_product_count = df_silver_pos.filter(~F.col("is_product_registered")).count()
print(f"[2] product_id未登録    : is_product_registered=false のレコード {unregistered_product_count} 件"
      f"（削除せずフラグで識別可能な状態。Gold layerのマスター未登録レポートで利用）")

# 3. store_id未登録
unregistered_store_count = df_silver_pos.filter(~F.col("is_store_registered")).count()
print(f"[3] store_id未登録      : is_store_registered=false のレコード {unregistered_store_count} 件"
      f"（削除せずフラグで識別可能な状態。Gold layerのマスター未登録レポートで利用）")

# 4. discount null
bronze_discount_null = df_bronze_pos.filter(F.col("discount_amount").isNull()).count()
silver_discount_null = df_silver_pos.filter(F.col("discount_amount").isNull()).count()
print(f"[4] discount null       : Bronzeでのnull {bronze_discount_null} 件 → "
      f"Silverでのnull {silver_discount_null} 件（0件が正しい。0円として補完済み）")

# 5. 時刻形式不一致
STANDARD_DATETIME_PATTERN = r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$"
bronze_time_mismatch = df_bronze_pos.filter(
    ~F.col("transaction_datetime").rlike(STANDARD_DATETIME_PATTERN)
).count()
silver_unparseable_timestamp = df_silver_pos.filter(F.col("transaction_timestamp").isNull()).count()
print(f"[5] 時刻形式不一致      : Bronzeでの非標準フォーマット {bronze_time_mismatch} 件 → "
      f"Silverで解析不能（transaction_timestamp=null）となった件数 {silver_unparseable_timestamp} 件"
      f"（複数フォーマット対応でほぼ解消。解析不能な極端な形式のみ残存）")

print("\n" + "-" * 80)
print(f"Bronze全件数: {df_bronze_pos.count()} 件 → Silver全件数（重複除去後）: {df_silver_pos.count()} 件")
print("-" * 80)

print("\n=== Silver layer 保存・品質チェック完了 ===")
