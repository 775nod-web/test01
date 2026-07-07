# Databricks ノートブック用
# Bronzeレイヤーに保存済みの各表について、サンプルデータと件数を表示する
#
# 前提：save_bronze_layer_tables.py を実行済みであること
#       （{カタログ}.bronze.bronze_* テーブルが存在すること）

CATALOG = spark.catalog.currentCatalog()
BRONZE_SCHEMA = f"{CATALOG}.bronze"

BRONZE_TABLES = [
    "bronze_pos_transactions",
    "bronze_product_master",
    "bronze_store_master",
    "bronze_member_master",
]

print(f"=== Bronzeスキーマ: {BRONZE_SCHEMA} ===\n")


# ──────────────────────────────────────────────
# 1. 各表のサンプルデータ表示
# ──────────────────────────────────────────────

table_counts = {}
for table_name in BRONZE_TABLES:
    full_name = f"{BRONZE_SCHEMA}.{table_name}"
    df = spark.table(full_name)
    count = df.count()
    table_counts[table_name] = count

    print(f"--- {full_name}（{count:,} 件） ---")
    df.show(10, truncate=False)


# ──────────────────────────────────────────────
# 2. 各表の件数サマリー
# ──────────────────────────────────────────────

print("\n" + "=" * 40)
print("=== Bronzeレイヤー 各表件数 ===")
print("=" * 40)
for table_name, count in table_counts.items():
    print(f"  {table_name:<28}: {count:>6,} 件")
print("=" * 40)
