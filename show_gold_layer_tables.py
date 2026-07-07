"""
小売メダリオンアーキテクチャ Goldレイヤー 表示スクリプト
（Databricks Free Edition Notebook 実行想定）

前提：save_gold_layer_tables.py を同セッションで実行済みで、
      goldスキーマに以下4表が保存されていること
        - gold.daily_sales_kpi
        - gold.store_daily_sales
        - gold.category_daily_sales
        - gold.data_quality_summary

本スクリプトは gold スキーマの各表について、
データ内容（全件）と表の件数を表示する。
"""

GOLD_TABLES = [
    "daily_sales_kpi",
    "store_daily_sales",
    "category_daily_sales",
    "data_quality_summary",
]

spark.sql("USE gold")

print("=" * 60)
print("=== Goldレイヤー 表データ・件数 ===")
print("=" * 60)

for table_name in GOLD_TABLES:
    df = spark.table(f"gold.{table_name}")
    row_count = df.count()

    print(f"\n--- gold.{table_name}（{row_count} 件） ---")
    df.show(50, truncate=False)

print("\n" + "=" * 60)
print("=== Goldレイヤー 件数サマリー ===")
print("=" * 60)
for table_name in GOLD_TABLES:
    row_count = spark.table(f"gold.{table_name}").count()
    print(f"  gold.{table_name:<24}: {row_count:>4,} 件")
