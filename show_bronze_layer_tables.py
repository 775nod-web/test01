"""
小売メダリオンアーキテクチャ Bronzeレイヤー 表示スクリプト
（Databricks Free Edition Notebook 実行想定）

前提：save_bronze_layer_tables.py を同セッションで実行済みで、
      bronzeスキーマに以下4表が保存されていること
        - bronze.store_master
        - bronze.product_master
        - bronze.member_master
        - bronze.pos_transactions

本スクリプトは bronze スキーマの4表について、
データ内容（サンプル行）と表の件数のみを表示する
（Bronzeレイヤーの範囲外であるデータ品質検出・集計は行わない）。
"""

spark.sql("USE bronze")

BRONZE_TABLES = [
    "store_master",
    "product_master",
    "member_master",
    "pos_transactions",
]

print("=" * 60)
print("=== Bronzeレイヤー 表データ・件数 ===")
print("=" * 60)

for table_name in BRONZE_TABLES:
    df = spark.table(f"bronze.{table_name}")
    row_count = df.count()

    print(f"\n--- bronze.{table_name}（{row_count} 件） ---")
    df.show(20, truncate=False)

print("\n" + "=" * 60)
print("=== Bronzeレイヤー 件数サマリー ===")
print("=" * 60)
for table_name in BRONZE_TABLES:
    row_count = spark.table(f"bronze.{table_name}").count()
    print(f"  bronze.{table_name:<20}: {row_count:>4,} 件")
