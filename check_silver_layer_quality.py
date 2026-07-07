# Databricks ノートブック用
# Silverレイヤーの品質改善が、Knowledge baseに定義した8種類の品質課題を
# Gold layer（日次/店舗別/カテゴリ別売上・データ品質サマリ）で使える水準まで
# クレンジングできているかを確認する
#
# 前提：bronze.bronze_* と silver.silver_* の両方が存在すること
#       （save_bronze_layer_tables.py と save_silver_layer_tables.py を実行済みであること）

from pyspark.sql import functions as F

CATALOG = spark.catalog.currentCatalog()
BRONZE_SCHEMA = f"{CATALOG}.bronze"
SILVER_SCHEMA = f"{CATALOG}.silver"

df_bronze_pos = spark.table(f"{BRONZE_SCHEMA}.bronze_pos_transactions")
df_bronze_product = spark.table(f"{BRONZE_SCHEMA}.bronze_product_master")

df_silver_pos = spark.table(f"{SILVER_SCHEMA}.silver_pos_transactions")
df_silver_rejected = spark.table(f"{SILVER_SCHEMA}.silver_pos_transactions_rejected")
df_silver_product = spark.table(f"{SILVER_SCHEMA}.silver_product_master")


# ──────────────────────────────────────────────
# 1. Bronze側の品質課題件数（改善前）を再計測
# ──────────────────────────────────────────────

valid_product_ids_bronze = [r.product_id for r in df_bronze_product.select("product_id").collect()]
valid_store_ids_bronze = [r.store_id for r in spark.table(f"{BRONZE_SCHEMA}.bronze_store_master").select("store_id").collect()]
bronze_dup = df_bronze_pos.groupBy("transaction_id").count().filter(F.col("count") > 1)
bronze_dup_extra = bronze_dup.agg(F.sum(F.col("count") - 1)).collect()[0][0] or 0

before_counts = {
    "transaction_idの重複（超過行）": bronze_dup_extra,
    "product_idマスター不一致": df_bronze_pos.filter(~F.col("product_id").isin(valid_product_ids_bronze)).count(),
    "store_idマスター不一致": df_bronze_pos.filter(~F.col("store_id").isin(valid_store_ids_bronze)).count(),
    "quantityが0または負の値": df_bronze_pos.filter(F.col("quantity") <= 0).count(),
    "unit_priceがnullまたは負の値": df_bronze_pos.filter(
        F.col("unit_price").isNull() | (F.col("unit_price") < 0)
    ).count(),
    "transaction_timestamp表記揺れ": df_bronze_pos.filter(
        ~F.col("transaction_timestamp").rlike(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")
    ).count(),
    "product categoryがnull": df_bronze_product.filter(F.col("category").isNull()).count(),
}


# ──────────────────────────────────────────────
# 2. Silver側（改善後）の品質チェック
#    silver_pos_transactionsはクレンジング済みのはずなので、すべて0件になることを確認する
# ──────────────────────────────────────────────

valid_product_ids_silver = [r.product_id for r in df_silver_product.select("product_id").collect()]
valid_store_ids_silver = [r.store_id for r in spark.table(f"{SILVER_SCHEMA}.silver_store_master").select("store_id").collect()]

after_dup = df_silver_pos.groupBy("transaction_id").count().filter(F.col("count") > 1)
after_dup_extra = after_dup.agg(F.sum(F.col("count") - 1)).collect()[0][0] or 0

after_counts = {
    "transaction_idの重複（超過行）": after_dup_extra,
    "product_idマスター不一致": df_silver_pos.filter(~F.col("product_id").isin(valid_product_ids_silver)).count(),
    "store_idマスター不一致": df_silver_pos.filter(~F.col("store_id").isin(valid_store_ids_silver)).count(),
    "quantityが0または負の値": df_silver_pos.filter(F.col("quantity") <= 0).count(),
    "unit_priceがnullまたは負の値": df_silver_pos.filter(
        F.col("unit_price").isNull() | (F.col("unit_price") < 0)
    ).count(),
    "transaction_timestamp表記揺れ（解析不能）": df_silver_pos.filter(F.col("transaction_ts").isNull()).count(),
    "product categoryがnull": df_silver_product.filter(F.col("category").isNull()).count(),
}

# customer_idがnullの件数は「非会員取引」として意図的に残しているため、
# 合否判定には含めず参考値として別掲する
customer_null_before = df_bronze_pos.filter(F.col("customer_id").isNull()).count()
customer_null_after = df_silver_pos.filter(F.col("customer_id").isNull()).count()


# ──────────────────────────────────────────────
# 3. Before/After 比較結果の表示
# ──────────────────────────────────────────────

print("=== データ品質課題 Before(Bronze) / After(Silver) 比較 ===\n")

all_resolved = True
issue_keys = [
    "product_idマスター不一致",
    "store_idマスター不一致",
    "transaction_idの重複（超過行）",
    "quantityが0または負の値",
    "unit_priceがnullまたは負の値",
    "transaction_timestamp表記揺れ",
    "product categoryがnull",
]
after_key_map = {
    "product_idマスター不一致": "product_idマスター不一致",
    "store_idマスター不一致": "store_idマスター不一致",
    "transaction_idの重複（超過行）": "transaction_idの重複（超過行）",
    "quantityが0または負の値": "quantityが0または負の値",
    "unit_priceがnullまたは負の値": "unit_priceがnullまたは負の値",
    "transaction_timestamp表記揺れ": "transaction_timestamp表記揺れ（解析不能）",
    "product categoryがnull": "product categoryがnull",
}

comparison_rows = []
for issue in issue_keys:
    before_value = before_counts[issue]
    after_value = after_counts[after_key_map[issue]]
    resolved = after_value == 0
    all_resolved = all_resolved and resolved
    comparison_rows.append((issue, int(before_value), int(after_value), "解消" if resolved else "未解消"))
    print(f"  [{'OK' if resolved else 'NG'}] {issue:<30} : before={before_value:>4,} 件 → after={after_value:>4,} 件")

df_comparison = spark.createDataFrame(
    comparison_rows,
    schema=["quality_issue", "before_bronze_count", "after_silver_count", "status"],
)
print("\n=== 品質課題 比較結果テーブル ===")
df_comparison.show(truncate=False)


# ──────────────────────────────────────────────
# 4. customer_idがnull（非会員取引）は参考値として表示
# ──────────────────────────────────────────────

print("=== 参考：customer_idがnull（非会員取引、除外対象ではない） ===")
print(f"  before(Bronze): {customer_null_before:,} 件 / after(Silver): {customer_null_after:,} 件")
print("  ※ 非会員取引は正当な売上データのため、クレンジングでは除外せずSilverにそのまま残している\n")


# ──────────────────────────────────────────────
# 5. 隔離表（silver_pos_transactions_rejected）の内訳確認
# ──────────────────────────────────────────────

print("=== 隔離データ（silver_pos_transactions_rejected）の理由別内訳 ===")
df_rejected_breakdown = (
    df_silver_rejected
    .withColumn("reject_reason", F.explode("reject_reasons"))
    .groupBy("reject_reason")
    .count()
    .orderBy(F.col("count").desc())
)
df_rejected_breakdown.show(truncate=False)

rejected_total = df_silver_rejected.count()
valid_total = df_silver_pos.count()
bronze_total = df_bronze_pos.count()
print(f"Bronze総件数: {bronze_total:,} 件 = Silver有効: {valid_total:,} 件 + Silver隔離: {rejected_total:,} 件")


# ──────────────────────────────────────────────
# 6. 総合判定
# ──────────────────────────────────────────────

print("\n" + "=" * 50)
if all_resolved and (bronze_total == valid_total + rejected_total):
    print("=== 総合判定: OK（Gold集計に使える水準まで品質課題は解消されています） ===")
else:
    print("=== 総合判定: NG（未解消の品質課題があります。上記の比較結果を確認してください） ===")
print("=" * 50)
