# Databricks ノートブック用
# sample スキーマに保存済みの小売サンプルデータ（POS/商品マスター/店舗マスター/会員マスター）について、
#   ・各表のサンプルデータ
#   ・各表の件数
#   ・品質課題データの件数
#   ・意図的に含めた品質課題一覧
# を表示する
#
# 前提：generate_retail_sample_data.py と save_sample_retail_tables.py を
#       同セッションで実行済みであること（sample.sample_* テーブルが存在すること）

from pyspark.sql import functions as F

df_pos = spark.table("sample.sample_pos_transactions")
df_product = spark.table("sample.sample_product_master")
df_store = spark.table("sample.sample_store_master")
df_member = spark.table("sample.sample_member_master")


# ──────────────────────────────────────────────
# 1. 各表のサンプルデータ表示
# ──────────────────────────────────────────────

print("=== POSトランザクション サンプル（10件） ===")
df_pos.show(10, truncate=False)

print("=== 商品マスター サンプル ===")
df_product.show(truncate=False)

print("=== 店舗マスター サンプル ===")
df_store.show(truncate=False)

print("=== 会員マスター サンプル（10件） ===")
df_member.show(10, truncate=False)


# ──────────────────────────────────────────────
# 2. 各表の全件数
# ──────────────────────────────────────────────

pos_count = df_pos.count()
product_count = df_product.count()
store_count = df_store.count()
member_count = df_member.count()

print("\n" + "=" * 40)
print("=== 各表 全件数 ===")
print("=" * 40)
print(f"  sample_pos_transactions : {pos_count:>6,} 件")
print(f"  sample_product_master   : {product_count:>6,} 件")
print(f"  sample_store_master     : {store_count:>6,} 件")
print(f"  sample_member_master    : {member_count:>6,} 件")


# ──────────────────────────────────────────────
# 3. 意図的に含めた品質課題ごとの件数集計
# ──────────────────────────────────────────────

valid_product_ids = [r.product_id for r in df_product.select("product_id").collect()]
valid_store_ids = [r.store_id for r in df_store.select("store_id").collect()]

# (1) product_idが商品マスターに存在しない
product_mismatch_count = df_pos.filter(
    ~F.col("product_id").isin(valid_product_ids)
).count()

# (2) store_idが店舗マスターに存在しない
store_mismatch_count = df_pos.filter(
    ~F.col("store_id").isin(valid_store_ids)
).count()

# (3) transaction_idの重複（重複によって発生した超過行数）
dup_group = df_pos.groupBy("transaction_id").count().filter(F.col("count") > 1)
duplicate_extra_rows = dup_group.agg(F.sum(F.col("count") - 1)).collect()[0][0] or 0

# (4) quantityが0または負の値
quantity_anomaly_count = df_pos.filter(F.col("quantity") <= 0).count()

# (5) unit_priceがnullまたは負の値
price_anomaly_count = df_pos.filter(
    F.col("unit_price").isNull() | (F.col("unit_price") < 0)
).count()

# (6) customer_idがnull
null_customer_count = df_pos.filter(F.col("customer_id").isNull()).count()

# (7) transaction_timestampのフォーマット/タイムゾーン表記揺れ
#     標準フォーマット（yyyy-MM-dd HH:mm:ss）に一致しないものを検出
STANDARD_TS_PATTERN = r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$"
timestamp_anomaly_count = df_pos.filter(
    ~F.col("transaction_timestamp").rlike(STANDARD_TS_PATTERN)
).count()

# (8) 商品カテゴリがnull
null_category_count = df_product.filter(F.col("category").isNull()).count()

print("\n" + "=" * 40)
print("=== 品質課題データの件数 ===")
print("=" * 40)
print(f"  [POS] product_idマスター不一致        : {product_mismatch_count:>4,} 件")
print(f"  [POS] store_idマスター不一致          : {store_mismatch_count:>4,} 件")
print(f"  [POS] transaction_id重複（超過行）     : {duplicate_extra_rows:>4,} 件")
print(f"  [POS] quantity異常（0/負値）           : {quantity_anomaly_count:>4,} 件")
print(f"  [POS] unit_price異常（null/負値）      : {price_anomaly_count:>4,} 件")
print(f"  [POS] customer_id null（非会員取引）   : {null_customer_count:>4,} 件")
print(f"  [POS] transaction_timestamp表記揺れ    : {timestamp_anomaly_count:>4,} 件")
print(f"  [商品マスター] category null           : {null_category_count:>4,} 件")


# ──────────────────────────────────────────────
# 4. 意図的に含めた品質課題一覧（サマリーテーブルとして表示）
# ──────────────────────────────────────────────

quality_summary_rows = [
    ("sample_pos_transactions", "product_idが商品マスターに存在しない", product_mismatch_count),
    ("sample_pos_transactions", "store_idが店舗マスターに存在しない", store_mismatch_count),
    ("sample_pos_transactions", "transaction_idの重複", int(duplicate_extra_rows)),
    ("sample_pos_transactions", "quantityが0または負の値", quantity_anomaly_count),
    ("sample_pos_transactions", "unit_priceがnullまたは負の値", price_anomaly_count),
    ("sample_pos_transactions", "customer_idがnull（非会員取引）", null_customer_count),
    ("sample_pos_transactions", "transaction_timestampのフォーマット/タイムゾーン表記揺れ", timestamp_anomaly_count),
    ("sample_product_master", "product categoryがnull", null_category_count),
]
df_quality_summary = spark.createDataFrame(
    quality_summary_rows,
    schema=["table_name", "quality_issue", "record_count"],
)

print("\n=== 意図的に含めた品質課題一覧 ===")
df_quality_summary.show(truncate=False)

total_quality_rows = sum(r[2] for r in quality_summary_rows)
print(f"品質課題対象レコード数 合計: {total_quality_rows:,} 件（8種類）")
