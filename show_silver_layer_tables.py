"""
小売メダリオンアーキテクチャ Silverレイヤー 表示スクリプト
（Databricks Free Edition Notebook 実行想定）

前提：save_silver_layer_tables.py を同セッションで実行済みで、
      silverスキーマに以下5表が保存されていること
        - silver.store_master
        - silver.product_master
        - silver.member_master
        - silver.pos_transactions            （品質改善後の正データ）
        - silver.pos_transactions_rejected    （品質課題により除外されたデータ）

本スクリプトは silver スキーマの各表について、
データ内容（サンプル行）と表の件数を表示する。
"""

SILVER_TABLES = [
    "store_master",
    "product_master",
    "member_master",
    "pos_transactions",
    "pos_transactions_rejected",
]

spark.sql("USE silver")

print("=" * 60)
print("=== Silverレイヤー 表データ・件数 ===")
print("=" * 60)

for table_name in SILVER_TABLES:
    df = spark.table(f"silver.{table_name}")
    row_count = df.count()

    print(f"\n--- silver.{table_name}（{row_count} 件） ---")
    df.show(20, truncate=False)

print("\n" + "=" * 60)
print("=== Silverレイヤー 件数サマリー ===")
print("=" * 60)
for table_name in SILVER_TABLES:
    row_count = spark.table(f"silver.{table_name}").count()
    print(f"  silver.{table_name:<28}: {row_count:>4,} 件")

bronze_pos_count = spark.table("bronze.pos_transactions").count()
silver_valid_count = spark.table("silver.pos_transactions").count()
silver_rejected_count = spark.table("silver.pos_transactions_rejected").count()
dedup_removed_count = bronze_pos_count - (silver_valid_count + silver_rejected_count)
print("\n--- 参考: pos_transactions の内訳 ---")
print(f"  bronze.pos_transactions            : {bronze_pos_count:>4,} 件（加工前）")
print(f"  うち transaction_id重複で除去      : {dedup_removed_count:>4,} 件")
print(f"  silver.pos_transactions（正データ） : {silver_valid_count:>4,} 件")
print(f"  silver.pos_transactions_rejected   : {silver_rejected_count:>4,} 件")
print(f"  検算: {silver_valid_count} + {silver_rejected_count} + {dedup_removed_count} = "
      f"{silver_valid_count + silver_rejected_count + dedup_removed_count} "
      f"({'OK' if silver_valid_count + silver_rejected_count + dedup_removed_count == bronze_pos_count else 'NG'})")
