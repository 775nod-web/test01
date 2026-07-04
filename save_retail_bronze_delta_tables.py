# Databricks ノートブック用
# 生成済み DataFrame（df_stores / df_products / df_customers / df_pos_sales）を
# Bronze レイヤーの Delta テーブルとして Hive メタストアに保存する
#
# 前提：generate_retail_medallion_sample_data.py を同セッションで実行済みであること
# 動作確認環境：Databricks Free Edition（Unity Catalog 不使用・Hive メタストア）

from pyspark.sql import functions as F

# ──────────────────────────────────────────────
# 0. 保存先データベース（スキーマ）の作成
# ──────────────────────────────────────────────

spark.sql("CREATE DATABASE IF NOT EXISTS bronze")
spark.sql("USE bronze")

print("データベース 'bronze' を選択しました")


# ──────────────────────────────────────────────
# 1. 店舗マスター → bronze_store_master
# ──────────────────────────────────────────────

(
    df_stores
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("bronze.bronze_store_master")
)
store_count = spark.table("bronze.bronze_store_master").count()
print(f"bronze_store_master 保存完了: {store_count:,} 件")


# ──────────────────────────────────────────────
# 2. 商品マスター → bronze_product_master
# ──────────────────────────────────────────────

(
    df_products
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("bronze.bronze_product_master")
)
product_count = spark.table("bronze.bronze_product_master").count()
print(f"bronze_product_master 保存完了: {product_count:,} 件")


# ──────────────────────────────────────────────
# 3. 顧客/会員データ → bronze_customer_master
# ──────────────────────────────────────────────

(
    df_customers
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("bronze.bronze_customer_master")
)
customer_count = spark.table("bronze.bronze_customer_master").count()
print(f"bronze_customer_master 保存完了: {customer_count:,} 件")


# ──────────────────────────────────────────────
# 4. POS売上イベント → bronze_pos_sales
# ──────────────────────────────────────────────

(
    df_pos_sales
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("bronze.bronze_pos_sales")
)
pos_sales_count = spark.table("bronze.bronze_pos_sales").count()
print(f"bronze_pos_sales 保存完了: {pos_sales_count:,} 件")


# ================================================================
# Output 4: 保存後のサンプルデータ・件数・品質課題件数の表示
# ================================================================

print("\n" + "=" * 80)
print("=== 各表のサンプルデータ（先頭5件） ===")
print("=" * 80)

print("\n--- bronze_store_master ---")
spark.table("bronze.bronze_store_master").show(5, truncate=False)

print("\n--- bronze_product_master ---")
spark.table("bronze.bronze_product_master").show(5, truncate=False)

print("\n--- bronze_customer_master ---")
spark.table("bronze.bronze_customer_master").show(5, truncate=False)

print("\n--- bronze_pos_sales ---")
spark.table("bronze.bronze_pos_sales").show(5, truncate=False)


print("\n" + "=" * 80)
print("=== 各表の件数サマリー ===")
print("=" * 80)
print(f"  bronze_store_master    : {store_count:>6,} 件")
print(f"  bronze_product_master  : {product_count:>6,} 件")
print(f"  bronze_customer_master : {customer_count:>6,} 件")
print(f"  bronze_pos_sales       : {pos_sales_count:>6,} 件")


# ──────────────────────────────────────────────
# 品質課題データの再検出（保存済みDeltaテーブルに対して実施）
# ──────────────────────────────────────────────

df_bronze_pos = spark.table("bronze.bronze_pos_sales")
valid_store_ids = [r.store_id for r in spark.table("bronze.bronze_store_master")
                    .select("store_id").collect()]
valid_product_ids = [r.product_id for r in spark.table("bronze.bronze_product_master")
                      .select("product_id").collect()]

dup_txn = df_bronze_pos.groupBy("transaction_id").count().filter(F.col("count") > 1)
dup_txn_total = dup_txn.agg(F.sum("count")).first()[0] or 0

unregistered_product_count = df_bronze_pos.filter(
    ~F.col("product_id").isin(valid_product_ids)
).count()

unregistered_store_count = df_bronze_pos.filter(
    ~F.col("store_id").isin(valid_store_ids)
).count()

discount_null_count = df_bronze_pos.filter(F.col("discount_amount").isNull()).count()

STANDARD_DATETIME_PATTERN = r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$"
time_mismatch_count = df_bronze_pos.filter(
    ~F.col("transaction_datetime").rlike(STANDARD_DATETIME_PATTERN)
).count()

print("\n" + "=" * 80)
print("=== 品質課題データの件数（bronze_pos_sales） ===")
print("=" * 80)
print(f"  重複 transaction_id     : {dup_txn_total:>4,} 件")
print(f"  product_id 未登録       : {unregistered_product_count:>4,} 件")
print(f"  store_id 未登録         : {unregistered_store_count:>4,} 件")
print(f"  discount_amount null    : {discount_null_count:>4,} 件")
print(f"  時刻形式不一致          : {time_mismatch_count:>4,} 件")

print("\n重複 transaction_id の内訳:")
dup_txn.show(truncate=False)

print("\nマスター未登録レポート（product_id未登録 または store_id未登録）:")
df_bronze_pos.filter(
    (~F.col("product_id").isin(valid_product_ids)) |
    (~F.col("store_id").isin(valid_store_ids))
).show(truncate=False)


# ──────────────────────────────────────────────
# 意図的に含めたデータ品質課題 一覧
# ──────────────────────────────────────────────

print("\n" + "=" * 80)
print("=== 意図的に含めたデータ品質課題 一覧（bronze_pos_sales） ===")
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

print("\n=== Bronzeレイヤー 保存・品質チェック完了 ===")
