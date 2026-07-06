# Databricks ノートブック用
# silver スキーマに保存した Silver レイヤーの表データと件数を表示する
#
# 前提：save_silver_tables.py を同セッションで実行済みであること
#       （silver.silver_users / silver_subscriptions / silver_user_events が存在すること）

SILVER_SCHEMA = "silver"
SILVER_TABLES = ["silver_users", "silver_subscriptions", "silver_user_events"]

print("=" * 60)
print(f"{SILVER_SCHEMA} レイヤー 保存結果表示")
print("=" * 60)

for table_name in SILVER_TABLES:
    full_name = f"{SILVER_SCHEMA}.{table_name}"
    df = spark.table(full_name)

    print(f"\n--- {full_name} ---")
    print(f"件数: {df.count():,} 件")
    df.show(20, truncate=False)

    valid_count = df.filter("is_valid_for_gold = true").count()
    invalid_count = df.filter("is_valid_for_gold = false").count()
    print(f"Gold集計に使用可能(is_valid_for_gold=True): {valid_count:,} 件")
    print(f"Gold集計から除外(is_valid_for_gold=False): {invalid_count:,} 件")

    if invalid_count > 0:
        print("除外レコードの内訳（dq_issues別）:")
        df.filter("is_valid_for_gold = false").groupBy("dq_issues").count().orderBy("dq_issues").show(truncate=False)
