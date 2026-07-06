# Databricks ノートブック用
# goldスキーマに投入したデータと件数を表示する（保存結果の確認）
#
# 前提：populate_gold_tables.py を同セッションで実行済みであること

GOLD_SCHEMA = "gold"
GOLD_TABLES = [
    "gold_daily_kpi",
    "gold_at_risk_users",
    "gold_data_quality_summary",
    "gold_user_ml_features",
]

print("=" * 60)
print(f"{GOLD_SCHEMA} レイヤー 保存結果表示")
print("=" * 60)

for table_name in GOLD_TABLES:
    full_name = f"{GOLD_SCHEMA}.{table_name}"
    df = spark.table(full_name)

    print(f"\n--- {full_name} ---")
    print(f"件数: {df.count():,} 件")
    df.orderBy(df.columns[0], df.columns[1] if len(df.columns) > 1 else df.columns[0]).show(20, truncate=False)

print("\n" + "=" * 60)
print("=== Gold層 保存結果表示 完了 ===")
print("=" * 60)
