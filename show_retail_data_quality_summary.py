"""
小売メダリオンアーキテクチャ サンプルデータ確認・データ品質サマリー表示スクリプト
（Databricks Free Edition Notebook 実行想定）

前提：generate_retail_medallion_sample_data.py を同セッションで実行済みで、
      sampleスキーマに以下4表が保存されていること
        - sample.store_master
        - sample.product_master
        - sample.member_master
        - sample.pos_transactions

本スクリプトは sample スキーマの4表を読み込み、
1. 各表のサンプルデータ・件数
2. 品質課題を持つデータの件数（実データから検出）
3. 意図的に含めた品質課題一覧
を表示する。
"""

from pyspark.sql import functions as F

spark.sql("USE sample")

df_stores   = spark.table("sample.store_master")
df_products = spark.table("sample.product_master")
df_members  = spark.table("sample.member_master")
df_pos      = spark.table("sample.pos_transactions")


# ──────────────────────────────────────────────
# 1. 各表のサンプルデータ・件数
# ──────────────────────────────────────────────

print("=" * 60)
print("=== 1. 各表のサンプルデータ・件数 ===")
print("=" * 60)

print(f"\n--- sample.store_master（{df_stores.count()} 件） ---")
df_stores.show(truncate=False)

print(f"\n--- sample.product_master（{df_products.count()} 件） ---")
df_products.show(truncate=False)

print(f"\n--- sample.member_master（{df_members.count()} 件） ---")
df_members.show(10, truncate=False)

print(f"\n--- sample.pos_transactions（{df_pos.count()} 件） ---")
df_pos.show(20, truncate=False)


# ──────────────────────────────────────────────
# 2. 品質課題を持つデータの件数（実データから検出）
# ──────────────────────────────────────────────

print("\n" + "=" * 60)
print("=== 2. 品質課題を持つデータの件数（検出結果） ===")
print("=" * 60)

# (a) 商品マスター不整合：product_masterに存在しないproduct_id
valid_product_ids = [r.product_id for r in df_products.select("product_id").collect()]
df_product_mismatch = df_pos.filter(~F.col("product_id").isin(valid_product_ids))
product_mismatch_count = df_product_mismatch.count()

# (b) 店舗マスター不整合：store_masterに存在しないstore_id
valid_store_ids = [r.store_id for r in df_stores.select("store_id").collect()]
df_store_mismatch = df_pos.filter(~F.col("store_id").isin(valid_store_ids))
store_mismatch_count = df_store_mismatch.count()

# (c) 取引ID重複：transaction_idが複数行に存在
df_dup_groups = df_pos.groupBy("transaction_id").count().filter(F.col("count") > 1)
dup_group_count = df_dup_groups.count()
dup_row_count = df_dup_groups.agg(F.sum("count")).collect()[0][0] or 0

# (d) 数量異常：quantityが0以下、またはnull
df_quantity_anomaly = df_pos.filter((F.col("quantity") <= 0) | F.col("quantity").isNull())
quantity_anomaly_count = df_quantity_anomaly.count()

# (e) 単価異常：unit_priceがnull、または負値
df_price_anomaly = df_pos.filter(F.col("unit_price").isNull() | (F.col("unit_price") < 0))
price_anomaly_count = df_price_anomaly.count()

# (f) timestamp表記揺れ：正常フォーマット（YYYY-MM-DD HH:MM:SS）に一致しないもの
NORMAL_TS_PATTERN = r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$"
df_timestamp_irregular = df_pos.filter(
    F.col("transaction_timestamp").isNotNull()
    & ~F.col("transaction_timestamp").rlike(NORMAL_TS_PATTERN)
)
timestamp_irregular_count = df_timestamp_irregular.count()

# (g) 会員ID欠損：customer_idがnull（非会員取引）
df_customer_null = df_pos.filter(F.col("customer_id").isNull())
customer_null_count = df_customer_null.count()

# (h) 商品カテゴリnull：product_masterのproduct_categoryがnull
df_category_null = df_products.filter(F.col("product_category").isNull())
category_null_count = df_category_null.count()

total_pos = df_pos.count()
total_products = df_products.count()

print(f"POSトランザクション総件数     : {total_pos} 件")
print(f"商品マスター総件数           : {total_products} 件")
print("-" * 60)
print(f"(a) 商品マスター不整合        : {product_mismatch_count} 件")
print(f"(b) 店舗マスター不整合        : {store_mismatch_count} 件")
print(f"(c) 取引ID重複                : {dup_group_count} 件のIDが重複（重複関係にある行数の合計: {dup_row_count} 行）")
print(f"(d) 数量異常（0または負値）    : {quantity_anomaly_count} 件")
print(f"(e) 単価異常（nullまたは負値） : {price_anomaly_count} 件")
print(f"(f) timestamp表記揺れ          : {timestamp_irregular_count} 件")
print(f"(g) 会員ID欠損（非会員取引）   : {customer_null_count} 件")
print(f"(h) 商品カテゴリ未設定         : {category_null_count} 件 / {total_products} 件")

print("\n--- 品質課題レコードのサンプル表示 ---")
print("商品マスター不整合の例:")
df_product_mismatch.show(5, truncate=False)
print("店舗マスター不整合の例:")
df_store_mismatch.show(5, truncate=False)
print("重複取引の例:")
df_pos.filter(F.col("transaction_id").isin(
    [r.transaction_id for r in df_dup_groups.select("transaction_id").collect()]
)).orderBy("transaction_id").show(10, truncate=False)
print("数量異常の例:")
df_quantity_anomaly.show(5, truncate=False)
print("単価異常の例:")
df_price_anomaly.show(5, truncate=False)
print("timestamp表記揺れの例:")
df_timestamp_irregular.show(10, truncate=False)
print("会員ID欠損の例:")
df_customer_null.show(5, truncate=False)
print("商品カテゴリ未設定の例:")
df_category_null.show(truncate=False)


# ──────────────────────────────────────────────
# 3. 意図的に含めた品質課題一覧
# ──────────────────────────────────────────────

print("\n" + "=" * 60)
print("=== 3. 意図的に含めた品質課題一覧 ===")
print("=" * 60)

quality_issue_summary = spark.createDataFrame([
    ("商品マスター不整合",        "pos_transactions", product_mismatch_count,   "product_idがproduct_masterに存在しない"),
    ("店舗マスター不整合",        "pos_transactions", store_mismatch_count,     "store_idがstore_masterに存在しない"),
    ("取引ID重複",                "pos_transactions", dup_group_count,          "transaction_idが重複している"),
    ("数量異常",                  "pos_transactions", quantity_anomaly_count,   "quantityが0または負の値"),
    ("単価異常",                  "pos_transactions", price_anomaly_count,      "unit_priceがnullまたは負の値"),
    ("timestamp表記揺れ",         "pos_transactions", timestamp_irregular_count, "transaction_timestampの形式やtimezoneが揺れている"),
    ("会員ID欠損",                "pos_transactions", customer_null_count,      "customer_idがnullの取引がある（非会員取引）"),
    ("商品カテゴリ未設定",        "product_master",    category_null_count,      "product_categoryがnullの商品がある"),
], ["quality_issue", "table_name", "record_count", "description"])

quality_issue_summary.show(truncate=False)
