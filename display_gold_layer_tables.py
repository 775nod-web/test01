# Databricks ノートブック用
# Goldレイヤーに保存済みの各表について、データと件数を表示する
#
# 前提：save_gold_layer_tables.py を実行済みであること
#       （{カタログ}.gold.gold_* テーブルが存在すること）

from pyspark.sql import functions as F

CATALOG = spark.catalog.currentCatalog()
GOLD_SCHEMA = f"{CATALOG}.gold"

print(f"=== Goldスキーマ: {GOLD_SCHEMA} ===\n")

table_counts = {}


# ──────────────────────────────────────────────
# 1. gold_daily_sales_kpi
# ──────────────────────────────────────────────

full_name = f"{GOLD_SCHEMA}.gold_daily_sales_kpi"
df = spark.table(full_name).orderBy("sales_date")
table_counts["gold_daily_sales_kpi"] = df.count()
print(f"--- {full_name}（{table_counts['gold_daily_sales_kpi']:,} 件） ---")
df.show(50, truncate=False)


# ──────────────────────────────────────────────
# 2. gold_store_daily_sales
# ──────────────────────────────────────────────

full_name = f"{GOLD_SCHEMA}.gold_store_daily_sales"
df = spark.table(full_name).orderBy("sales_date", "store_id")
table_counts["gold_store_daily_sales"] = df.count()
print(f"--- {full_name}（{table_counts['gold_store_daily_sales']:,} 件） ---")
df.show(20, truncate=False)


# ──────────────────────────────────────────────
# 3. gold_category_daily_sales
# ──────────────────────────────────────────────

full_name = f"{GOLD_SCHEMA}.gold_category_daily_sales"
df = spark.table(full_name).orderBy("sales_date", "category")
table_counts["gold_category_daily_sales"] = df.count()
print(f"--- {full_name}（{table_counts['gold_category_daily_sales']:,} 件） ---")
df.show(20, truncate=False)


# ──────────────────────────────────────────────
# 4. gold_data_quality_summary
# ──────────────────────────────────────────────

full_name = f"{GOLD_SCHEMA}.gold_data_quality_summary"
df = spark.table(full_name).orderBy(F.col("record_count").desc())
table_counts["gold_data_quality_summary"] = df.count()
print(f"--- {full_name}（{table_counts['gold_data_quality_summary']:,} 件） ---")
df.show(20, truncate=False)


# ──────────────────────────────────────────────
# 5. 各表の件数サマリー
# ──────────────────────────────────────────────

print("\n" + "=" * 40)
print("=== Goldレイヤー 各表件数 ===")
print("=" * 40)
for table_name, count in table_counts.items():
    print(f"  {table_name:<28}: {count:>6,} 件")
print("=" * 40)
