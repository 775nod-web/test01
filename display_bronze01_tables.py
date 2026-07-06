# Databricks ノートブック用
# bronze01 スキーマに保存した Bronze レイヤーの表データと件数を表示する
#
# 前提：save_bronze01_tables.py を同セッションで実行済みであること
#       （bronze01.bronze_users / bronze_subscriptions / bronze_user_events が存在すること）

BRONZE_SCHEMA = "bronze01"
BRONZE_TABLES = ["bronze_users", "bronze_subscriptions", "bronze_user_events"]

print("=" * 60)
print(f"{BRONZE_SCHEMA} レイヤー 保存結果表示")
print("=" * 60)

for table_name in BRONZE_TABLES:
    full_name = f"{BRONZE_SCHEMA}.{table_name}"
    df = spark.table(full_name)

    print(f"\n--- {full_name} ---")
    print(f"件数: {df.count():,} 件")
    df.show(20, truncate=False)
