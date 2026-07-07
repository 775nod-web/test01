"""
Silver レイヤー データ確認スクリプト（Databricks Free Edition Notebook 用）

前提: create_silver_layer_tables.py を実行済みで、
      silver.customer_master / silver.contract_data / silver.support_tickets
      が Delta テーブルとして保存されていること。

Silverレイヤーとして保存した各表のデータと件数を表示する。
"""

# ──────────────────────────────────────────────
# 0. silver スキーマのテーブル一覧
# ──────────────────────────────────────────────

print("=== silver スキーマのテーブル一覧 ===")
spark.sql("SHOW TABLES IN silver").show(truncate=False)


# ──────────────────────────────────────────────
# 1. 各表のデータ・件数
# ──────────────────────────────────────────────

df_customer_master = spark.table("silver.customer_master")
df_contract_data = spark.table("silver.contract_data")
df_support_tickets = spark.table("silver.support_tickets")

print(f"\n=== silver.customer_master（全 {df_customer_master.count()} 件） ===")
display(df_customer_master)

print(f"\n=== silver.contract_data（全 {df_contract_data.count()} 件） ===")
display(df_contract_data)

print(f"\n=== silver.support_tickets（全 {df_support_tickets.count()} 件） ===")
display(df_support_tickets)


# ──────────────────────────────────────────────
# 2. 各表の件数サマリ
# ──────────────────────────────────────────────

table_record_counts = spark.createDataFrame(
    [
        ("silver.customer_master", df_customer_master.count()),
        ("silver.contract_data", df_contract_data.count()),
        ("silver.support_tickets", df_support_tickets.count()),
    ],
    ["table_name", "record_count"],
)

print("\n=== Silverレイヤー 各表の件数サマリ ===")
display(table_record_counts)


# ──────────────────────────────────────────────
# 3. （参考）品質改善内容の確認
#    data_quality_flags が付与されているレコード数と、
#    優先度・ステータスが正規値に標準化されていることを確認
# ──────────────────────────────────────────────

from pyspark.sql import functions as F

flagged_count = df_support_tickets.filter(F.size("data_quality_flags") > 0).count()
print(f"\n品質課題フラグが記録されているチケット: {flagged_count} 件 / 全 {df_support_tickets.count()} 件")

print("\n優先度の値一覧（標準化後）:")
df_support_tickets.groupBy("priority").count().orderBy("priority").show()

print("ステータスの値一覧（標準化後）:")
df_support_tickets.groupBy("status").count().orderBy("status").show()
