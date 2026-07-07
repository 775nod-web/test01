"""
Bronze レイヤー データ確認スクリプト（Databricks Free Edition Notebook 用）

前提: save_bronze_layer_tables.py を実行済みで、
      bronze.customer_master / bronze.contract_data / bronze.support_tickets
      が Delta テーブルとして保存されていること。

Bronzeレイヤーとして保存した各表のデータと件数を表示する。
"""

# ──────────────────────────────────────────────
# 0. bronze スキーマのテーブル一覧
# ──────────────────────────────────────────────

print("=== bronze スキーマのテーブル一覧 ===")
spark.sql("SHOW TABLES IN bronze").show(truncate=False)


# ──────────────────────────────────────────────
# 1. 各表のデータ・件数
# ──────────────────────────────────────────────

df_customer_master = spark.table("bronze.customer_master")
df_contract_data = spark.table("bronze.contract_data")
df_support_tickets = spark.table("bronze.support_tickets")

print(f"\n=== bronze.customer_master（全 {df_customer_master.count()} 件） ===")
display(df_customer_master)  # Databricksノートブックの display() で表形式表示

print(f"\n=== bronze.contract_data（全 {df_contract_data.count()} 件） ===")
display(df_contract_data)

print(f"\n=== bronze.support_tickets（全 {df_support_tickets.count()} 件） ===")
display(df_support_tickets)


# ──────────────────────────────────────────────
# 2. 各表の件数サマリ
# ──────────────────────────────────────────────

table_record_counts = spark.createDataFrame(
    [
        ("bronze.customer_master", df_customer_master.count()),
        ("bronze.contract_data", df_contract_data.count()),
        ("bronze.support_tickets", df_support_tickets.count()),
    ],
    ["table_name", "record_count"],
)

print("\n=== Bronzeレイヤー 各表の件数サマリ ===")
display(table_record_counts)
