# Databricks ノートブック用
# Silverレイヤーのデータを集計し、Gold layerの表として保存する
#
# 前提：silver.silver_pos_transactions / silver_pos_transactions_rejected /
#       silver_product_master / silver_store_master が存在すること
#       （save_silver_layer_tables.py を実行済みであること）
# 動作確認環境：Databricks Free Edition（Unity Catalog）
#
# Gold表の設計（Knowledge base「Gold出力」に対応）
#   - gold_daily_sales_kpi        : 日次の総売上・取引数・販売数量・平均客単価
#   - gold_store_daily_sales      : 店舗別・日別の売上・取引数・販売数量
#   - gold_category_daily_sales   : 商品カテゴリ別・日別の売上・販売数量・平均単価
#   - gold_data_quality_summary   : product_id/store_id不一致・重複・quantity/unit_price異常の件数

from pyspark.sql import functions as F
from datetime import datetime

CATALOG = spark.catalog.currentCatalog()
SILVER_SCHEMA = f"{CATALOG}.silver"
GOLD_SCHEMA = f"{CATALOG}.gold"

CHECKED_AT = datetime.now()

# ──────────────────────────────────────────────
# 0. Goldスキーマ・表の作成
#    列構成を明示して CREATE OR REPLACE TABLE で（再）作成することで、
#    過去の試行等で異なる列構成の表が既に存在していても、
#    実行のたびに必ずこの設計どおりのスキーマへ揃える。
#    （CREATE TABLE IF NOT EXISTS だと、既存表の列構成が古い/異なる場合に
#      そのまま残ってしまい、後続のINSERTで列数不一致エラーになるため）
# ──────────────────────────────────────────────

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {GOLD_SCHEMA}")
print(f"スキーマ '{GOLD_SCHEMA}' を使用します")

spark.sql(f"""
CREATE OR REPLACE TABLE {GOLD_SCHEMA}.gold_daily_sales_kpi (
    sales_date         DATE,
    total_sales        DOUBLE,
    transaction_count  BIGINT,
    total_quantity     BIGINT,
    avg_customer_spend DOUBLE
) USING DELTA
""")

spark.sql(f"""
CREATE OR REPLACE TABLE {GOLD_SCHEMA}.gold_store_daily_sales (
    sales_date        DATE,
    store_id          STRING,
    store_name        STRING,
    region            STRING,
    total_sales       DOUBLE,
    transaction_count BIGINT,
    total_quantity    BIGINT
) USING DELTA
""")

spark.sql(f"""
CREATE OR REPLACE TABLE {GOLD_SCHEMA}.gold_category_daily_sales (
    sales_date     DATE,
    category       STRING,
    total_sales    DOUBLE,
    total_quantity BIGINT,
    avg_unit_price DOUBLE
) USING DELTA
""")

spark.sql(f"""
CREATE OR REPLACE TABLE {GOLD_SCHEMA}.gold_data_quality_summary (
    quality_issue STRING,
    record_count  BIGINT,
    checked_at    TIMESTAMP
) USING DELTA
""")


# ──────────────────────────────────────────────
# 1. Silver表の読み込み
# ──────────────────────────────────────────────

df_silver_pos = spark.table(f"{SILVER_SCHEMA}.silver_pos_transactions")
df_silver_product = spark.table(f"{SILVER_SCHEMA}.silver_product_master")
df_silver_store = spark.table(f"{SILVER_SCHEMA}.silver_store_master")
df_silver_rejected = spark.table(f"{SILVER_SCHEMA}.silver_pos_transactions_rejected")


# ──────────────────────────────────────────────
# 2. gold_daily_sales_kpi：日次の総売上・取引数・販売数量・平均客単価
# ──────────────────────────────────────────────

df_daily_kpi = (
    df_silver_pos
    .groupBy(F.col("transaction_date").alias("sales_date"))
    .agg(
        F.sum("sales_amount").alias("total_sales"),
        F.countDistinct("transaction_id").alias("transaction_count"),
        F.sum("quantity").alias("total_quantity"),
    )
    .withColumn("avg_customer_spend", F.col("total_sales") / F.col("transaction_count"))
    .select("sales_date", "total_sales", "transaction_count", "total_quantity", "avg_customer_spend")
)


# ──────────────────────────────────────────────
# 3. gold_store_daily_sales：店舗別・日別の売上・取引数・販売数量
# ──────────────────────────────────────────────

df_store_daily = (
    df_silver_pos
    .groupBy(F.col("transaction_date").alias("sales_date"), "store_id")
    .agg(
        F.sum("sales_amount").alias("total_sales"),
        F.countDistinct("transaction_id").alias("transaction_count"),
        F.sum("quantity").alias("total_quantity"),
    )
    .join(df_silver_store.select("store_id", "store_name", "region"), on="store_id", how="left")
    .select("sales_date", "store_id", "store_name", "region", "total_sales", "transaction_count", "total_quantity")
)


# ──────────────────────────────────────────────
# 4. gold_category_daily_sales：カテゴリ別・日別の売上・販売数量・平均単価
# ──────────────────────────────────────────────

df_category_daily = (
    df_silver_pos
    .join(df_silver_product.select("product_id", "category"), on="product_id", how="left")
    .groupBy(F.col("transaction_date").alias("sales_date"), "category")
    .agg(
        F.sum("sales_amount").alias("total_sales"),
        F.sum("quantity").alias("total_quantity"),
        F.avg("unit_price").alias("avg_unit_price"),
    )
    .select("sales_date", "category", "total_sales", "total_quantity", "avg_unit_price")
)


# ──────────────────────────────────────────────
# 5. gold_data_quality_summary：Silverで隔離した理由別の件数
#    Knowledge baseのGold出力定義に合わせ、5種類の課題を漏れなく（0件でも）表示する
# ──────────────────────────────────────────────

REASON_LABELS = [
    ("product_id_not_in_master", "product_idマスター不一致"),
    ("store_id_not_in_master", "store_idマスター不一致"),
    ("duplicate_transaction_id", "transaction_id重複"),
    ("quantity_invalid", "quantity異常"),
    ("unit_price_invalid", "unit_price異常"),
]
df_reason_master = spark.createDataFrame(REASON_LABELS, schema=["reject_reason", "quality_issue"])

df_rejected_counts = (
    df_silver_rejected
    .withColumn("reject_reason", F.explode("reject_reasons"))
    .groupBy("reject_reason")
    .count()
)

df_quality_summary = (
    df_reason_master
    .join(df_rejected_counts, on="reject_reason", how="left")
    .withColumn("record_count", F.coalesce(F.col("count"), F.lit(0)).cast("long"))
    .withColumn("checked_at", F.lit(CHECKED_AT).cast("timestamp"))
    .select("quality_issue", "record_count", "checked_at")
)


# ──────────────────────────────────────────────
# 6. Gold表へ保存（INSERT OVERWRITE：直前にCREATE OR REPLACEした表定義に対してデータを入れる）
# ──────────────────────────────────────────────

def save_gold_table(df, table_name: str, columns: list) -> int:
    full_name = f"{GOLD_SCHEMA}.{table_name}"
    temp_view = f"_tmp_{table_name}"
    df.select(*columns).createOrReplaceTempView(temp_view)
    spark.sql(f"INSERT OVERWRITE TABLE {full_name} SELECT {', '.join(columns)} FROM {temp_view}")
    count = spark.table(full_name).count()
    print(f"{full_name} 保存完了: {count:,} 件")
    return count


gold_counts = {
    "gold_daily_sales_kpi": save_gold_table(
        df_daily_kpi, "gold_daily_sales_kpi",
        ["sales_date", "total_sales", "transaction_count", "total_quantity", "avg_customer_spend"],
    ),
    "gold_store_daily_sales": save_gold_table(
        df_store_daily, "gold_store_daily_sales",
        ["sales_date", "store_id", "store_name", "region", "total_sales", "transaction_count", "total_quantity"],
    ),
    "gold_category_daily_sales": save_gold_table(
        df_category_daily, "gold_category_daily_sales",
        ["sales_date", "category", "total_sales", "total_quantity", "avg_unit_price"],
    ),
    "gold_data_quality_summary": save_gold_table(
        df_quality_summary, "gold_data_quality_summary",
        ["quality_issue", "record_count", "checked_at"],
    ),
}

print("\n" + "=" * 40)
print(f"=== {GOLD_SCHEMA} 保存完了サマリー ===")
print("=" * 40)
for table_name, count in gold_counts.items():
    print(f"  {table_name:<28}: {count:>6,} 件")
print("=" * 40)
