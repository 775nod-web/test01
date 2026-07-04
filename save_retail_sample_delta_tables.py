# Databricks ノートブック用
# 生成済み DataFrame（df_stores / df_products / df_customers / df_pos_sales）を
# サンプルデータとして Delta テーブルに保存する
#
# 注：ここでは Bronze レイヤーとしての取り込み（Auto Loader / 取り込み時刻列の付与等）は
#     行わず、あくまで「生成したサンプルデータをそのまま保存する」ことのみを目的とする。
#     Bronze レイヤーとしての本実装は後続の別タスクで対応する。
#
# 前提：generate_retail_medallion_sample_data.py と同じフォルダに配置されていること
# 動作確認環境：Databricks Free Edition（Unity Catalog 不使用・Hive メタストア）

from pyspark.sql import functions as F

# ──────────────────────────────────────────────
# 0-1. 依存データ（サンプルDataFrame）の読み込み
#      df_stores 等が未定義（本スクリプトを単独実行した場合）は、
#      同じフォルダの generate_retail_medallion_sample_data.py を読み込んで実行し、
#      サンプルデータの DataFrame を生成する。
#      同一ノートブックで generate 側をすでに実行済みの場合は再生成しない。
# ──────────────────────────────────────────────

if "df_stores" not in dir():
    with open("generate_retail_medallion_sample_data.py", encoding="utf-8") as f:
        exec(f.read(), globals())


# ──────────────────────────────────────────────
# 0-2. 保存先データベース（スキーマ）の作成
# ──────────────────────────────────────────────

spark.sql("CREATE DATABASE IF NOT EXISTS sample")
spark.sql("USE sample")

print("データベース 'sample' を選択しました")


# ──────────────────────────────────────────────
# 1. 店舗マスター → sample.store_master
# ──────────────────────────────────────────────

(
    df_stores
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("sample.store_master")
)
store_count = spark.table("sample.store_master").count()
print(f"sample.store_master 保存完了: {store_count:,} 件")


# ──────────────────────────────────────────────
# 2. 商品マスター → sample.product_master
# ──────────────────────────────────────────────

(
    df_products
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("sample.product_master")
)
product_count = spark.table("sample.product_master").count()
print(f"sample.product_master 保存完了: {product_count:,} 件")


# ──────────────────────────────────────────────
# 3. 顧客/会員データ → sample.customer_master
# ──────────────────────────────────────────────

(
    df_customers
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("sample.customer_master")
)
customer_count = spark.table("sample.customer_master").count()
print(f"sample.customer_master 保存完了: {customer_count:,} 件")


# ──────────────────────────────────────────────
# 4. POS売上イベント → sample.pos_sales
# ──────────────────────────────────────────────

(
    df_pos_sales
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("sample.pos_sales")
)
pos_sales_count = spark.table("sample.pos_sales").count()
print(f"sample.pos_sales 保存完了: {pos_sales_count:,} 件")


# ================================================================
# Output 4: 保存後のサンプルデータ・件数・品質課題件数の表示
# ================================================================

print("\n" + "=" * 80)
print("=== 各表のサンプルデータ（先頭5件） ===")
print("=" * 80)

print("\n--- sample.store_master ---")
spark.table("sample.store_master").show(5, truncate=False)

print("\n--- sample.product_master ---")
spark.table("sample.product_master").show(5, truncate=False)

print("\n--- sample.customer_master ---")
spark.table("sample.customer_master").show(5, truncate=False)

print("\n--- sample.pos_sales ---")
spark.table("sample.pos_sales").show(5, truncate=False)


print("\n" + "=" * 80)
print("=== 各表の件数サマリー ===")
print("=" * 80)
print(f"  sample.store_master    : {store_count:>6,} 件")
print(f"  sample.product_master  : {product_count:>6,} 件")
print(f"  sample.customer_master : {customer_count:>6,} 件")
print(f"  sample.pos_sales       : {pos_sales_count:>6,} 件")


# ──────────────────────────────────────────────
# 品質課題データの再検出（保存済みDeltaテーブルに対して実施）
# ──────────────────────────────────────────────

df_sample_pos = spark.table("sample.pos_sales")
valid_store_ids = [r.store_id for r in spark.table("sample.store_master")
                    .select("store_id").collect()]
valid_product_ids = [r.product_id for r in spark.table("sample.product_master")
                      .select("product_id").collect()]

dup_txn = df_sample_pos.groupBy("transaction_id").count().filter(F.col("count") > 1)
dup_txn_total = dup_txn.agg(F.sum("count")).first()[0] or 0

unregistered_product_count = df_sample_pos.filter(
    ~F.col("product_id").isin(valid_product_ids)
).count()

unregistered_store_count = df_sample_pos.filter(
    ~F.col("store_id").isin(valid_store_ids)
).count()

discount_null_count = df_sample_pos.filter(F.col("discount_amount").isNull()).count()

STANDARD_DATETIME_PATTERN = r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$"
time_mismatch_count = df_sample_pos.filter(
    ~F.col("transaction_datetime").rlike(STANDARD_DATETIME_PATTERN)
).count()

print("\n" + "=" * 80)
print("=== 品質課題データの件数（sample.pos_sales） ===")
print("=" * 80)
print(f"  重複 transaction_id     : {dup_txn_total:>4,} 件")
print(f"  product_id 未登録       : {unregistered_product_count:>4,} 件")
print(f"  store_id 未登録         : {unregistered_store_count:>4,} 件")
print(f"  discount_amount null    : {discount_null_count:>4,} 件")
print(f"  時刻形式不一致          : {time_mismatch_count:>4,} 件")

print("\n重複 transaction_id の内訳:")
dup_txn.show(truncate=False)

print("\nマスター未登録レポート（product_id未登録 または store_id未登録）:")
df_sample_pos.filter(
    (~F.col("product_id").isin(valid_product_ids)) |
    (~F.col("store_id").isin(valid_store_ids))
).show(truncate=False)


# ──────────────────────────────────────────────
# 意図的に含めたデータ品質課題 一覧
# ──────────────────────────────────────────────

print("\n" + "=" * 80)
print("=== 意図的に含めたデータ品質課題 一覧（sample.pos_sales） ===")
print("=" * 80)
quality_issues = [
    ("重複transaction",   5, "同一 transaction_id を持つレコードが重複して存在する"),
    ("product_id未登録",  5, "product_master に存在しない product_id を持つ取引がある"),
    ("store_id未登録",    5, "store_master に存在しない store_id を持つ取引がある"),
    ("discount null",    10, "discount_amount が NULL（値引きなしの0円とは区別すべき欠損値）"),
    ("時刻形式不一致",    10, "transaction_datetime が標準フォーマット以外の複数形式で混在している"),
]
for name, count, desc in quality_issues:
    print(f"  ・{name:<16} : {count:>2} 件 … {desc}")

print("\n=== サンプルデータ 保存・品質チェック完了 ===")
