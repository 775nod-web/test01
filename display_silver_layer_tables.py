# Databricks ノートブック用
# Silverレイヤーに保存済みの各表について、サンプルデータと件数を表示する
#
# 前提：save_silver_layer_tables.py を実行済みであること
#       （{カタログ}.silver.silver_* テーブルが存在すること）

CATALOG = spark.catalog.currentCatalog()
SILVER_SCHEMA = f"{CATALOG}.silver"

SILVER_TABLES = [
    "silver_pos_transactions",
    "silver_pos_transactions_rejected",
    "silver_product_master",
    "silver_store_master",
    "silver_member_master",
]

print(f"=== Silverスキーマ: {SILVER_SCHEMA} ===\n")


# ──────────────────────────────────────────────
# 1. 各表のサンプルデータ表示
# ──────────────────────────────────────────────

table_counts = {}
for table_name in SILVER_TABLES:
    full_name = f"{SILVER_SCHEMA}.{table_name}"
    df = spark.table(full_name)
    count = df.count()
    table_counts[table_name] = count

    print(f"--- {full_name}（{count:,} 件） ---")
    df.show(10, truncate=False)


# ──────────────────────────────────────────────
# 2. 各表の件数サマリー
# ──────────────────────────────────────────────

print("\n" + "=" * 40)
print("=== Silverレイヤー 各表件数 ===")
print("=" * 40)
for table_name, count in table_counts.items():
    print(f"  {table_name:<34}: {count:>6,} 件")
print("=" * 40)
