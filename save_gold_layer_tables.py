"""
小売メダリオンアーキテクチャ Goldレイヤー保存スクリプト
（Databricks Free Edition Notebook 実行想定）

前提：save_silver_layer_tables.py を同セッションで実行済みで、
      silverスキーマに以下の表が保存されていること
        - silver.store_master
        - silver.product_master
        - silver.pos_transactions（品質改善後の正データ）

本スクリプトは silver スキーマの正データを集計し、
Knowledge baseの「#Gold出力」に定義された4表として gold スキーマへ保存する。

  - gold.daily_sales_kpi     : 日次の総売上・取引数・販売数量・平均客単価
  - gold.store_daily_sales   : 店舗別・日ごとの売上・取引数量
  - gold.category_daily_sales: 商品カテゴリー別・日別売上・販売数量・平均単価
  - gold.data_quality_summary: product_id不一致・store_id不一致・
                                重複トランザクション・quantity異常・価格異常
                                （bronzeの生データを対象に検出した件数）
"""

from pyspark.sql import functions as F

spark.sql("CREATE SCHEMA IF NOT EXISTS gold")
print("スキーマ 'gold' を確認/作成しました")


# ──────────────────────────────────────────────
# 1. Silverレイヤーの読み込み・共通加工
# ──────────────────────────────────────────────

df_pos     = spark.table("silver.pos_transactions")
df_stores  = spark.table("silver.store_master")
df_products = spark.table("silver.product_master")

# 売上金額・集計用の日付列を付与し、店舗名・商品カテゴリを結合
df_pos_enriched = (
    df_pos
    .withColumn("sales_date", F.to_date("transaction_timestamp"))
    .withColumn("sales_amount", F.col("quantity") * F.col("unit_price"))
    .join(df_stores.select("store_id", "store_name"), on="store_id", how="left")
    .join(df_products.select("product_id", "product_category"), on="product_id", how="left")
)


# ──────────────────────────────────────────────
# 2. gold.daily_sales_kpi：日次売上KPI
#    総売上・取引数・販売数量・平均客単価
# ──────────────────────────────────────────────

df_daily_sales_kpi = (
    df_pos_enriched
    .groupBy("sales_date")
    .agg(
        F.round(F.sum("sales_amount"), 2).alias("total_sales_amount"),
        F.countDistinct("transaction_id").alias("transaction_count"),
        F.sum("quantity").alias("total_quantity"),
    )
    .withColumn(
        "avg_customer_spend",
        F.round(F.col("total_sales_amount") / F.col("transaction_count"), 2),
    )
    .orderBy("sales_date")
)


# ──────────────────────────────────────────────
# 3. gold.store_daily_sales：店舗別・日ごとの売上
# ──────────────────────────────────────────────

df_store_daily_sales = (
    df_pos_enriched
    .groupBy("sales_date", "store_id", "store_name")
    .agg(
        F.round(F.sum("sales_amount"), 2).alias("total_sales_amount"),
        F.countDistinct("transaction_id").alias("transaction_count"),
        F.sum("quantity").alias("total_quantity"),
    )
    .orderBy("sales_date", "store_id")
)


# ──────────────────────────────────────────────
# 4. gold.category_daily_sales：カテゴリー別・日別売上
# ──────────────────────────────────────────────

df_category_daily_sales = (
    df_pos_enriched
    .groupBy("sales_date", "product_category")
    .agg(
        F.round(F.sum("sales_amount"), 2).alias("total_sales_amount"),
        F.sum("quantity").alias("total_quantity"),
        F.round(F.avg("unit_price"), 2).alias("avg_unit_price"),
    )
    .orderBy("sales_date", "product_category")
)


# ──────────────────────────────────────────────
# 5. gold.data_quality_summary：データ品質サマリ
#    bronze（生データ）を対象に、Gold出力仕様の5項目を検出する
# ──────────────────────────────────────────────

df_bronze_pos      = spark.table("bronze.pos_transactions")
df_bronze_stores   = spark.table("bronze.store_master")
df_bronze_products = spark.table("bronze.product_master")

valid_store_ids_bronze   = [r.store_id for r in df_bronze_stores.select("store_id").collect()]
valid_product_ids_bronze = [r.product_id for r in df_bronze_products.select("product_id").collect()]

product_mismatch_count = df_bronze_pos.filter(~F.col("product_id").isin(valid_product_ids_bronze)).count()
store_mismatch_count   = df_bronze_pos.filter(~F.col("store_id").isin(valid_store_ids_bronze)).count()
duplicate_count         = df_bronze_pos.groupBy("transaction_id").count().filter(F.col("count") > 1).count()
quantity_anomaly_count  = df_bronze_pos.filter((F.col("quantity") <= 0) | F.col("quantity").isNull()).count()
price_anomaly_count     = df_bronze_pos.filter(F.col("unit_price").isNull() | (F.col("unit_price") < 0)).count()

df_data_quality_summary = spark.createDataFrame(
    [
        ("product_id不一致",       product_mismatch_count, "product_idがproduct_masterに存在しない"),
        ("store_id不一致",         store_mismatch_count,   "store_idがstore_masterに存在しない"),
        ("重複トランザクション",    duplicate_count,         "transaction_idが重複している"),
        ("quantity異常",           quantity_anomaly_count,  "quantityが0または負の値"),
        ("価格異常",               price_anomaly_count,     "unit_priceがnullまたは負の値"),
    ],
    ["quality_issue", "record_count", "description"],
)


# ──────────────────────────────────────────────
# 6. goldスキーマへの保存
# ──────────────────────────────────────────────

(df_daily_sales_kpi.write.format("delta").mode("overwrite")
 .option("overwriteSchema", "true").saveAsTable("gold.daily_sales_kpi"))
(df_store_daily_sales.write.format("delta").mode("overwrite")
 .option("overwriteSchema", "true").saveAsTable("gold.store_daily_sales"))
(df_category_daily_sales.write.format("delta").mode("overwrite")
 .option("overwriteSchema", "true").saveAsTable("gold.category_daily_sales"))
(df_data_quality_summary.write.format("delta").mode("overwrite")
 .option("overwriteSchema", "true").saveAsTable("gold.data_quality_summary"))

print("\n=== Goldレイヤー保存完了 ===")
print(f"  gold.daily_sales_kpi      : {spark.table('gold.daily_sales_kpi').count():>4,} 件")
print(f"  gold.store_daily_sales    : {spark.table('gold.store_daily_sales').count():>4,} 件")
print(f"  gold.category_daily_sales : {spark.table('gold.category_daily_sales').count():>4,} 件")
print(f"  gold.data_quality_summary : {spark.table('gold.data_quality_summary').count():>4,} 件")
