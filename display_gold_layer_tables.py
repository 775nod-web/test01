"""
Gold レイヤー データ確認スクリプト（Databricks Free Edition Notebook 用）

前提: create_gold_layer_tables.py を実行済みで、
      gold.daily_support_kpi / gold.customer_support_risk /
      gold.category_support_summary / gold.data_quality_summary
      が Delta テーブルとして保存されていること。

Goldレイヤーとして保存した各表のデータと件数を表示する。
"""

# ──────────────────────────────────────────────
# 0. gold スキーマのテーブル一覧
# ──────────────────────────────────────────────

print("=== gold スキーマのテーブル一覧 ===")
spark.sql("SHOW TABLES IN gold").show(truncate=False)


# ──────────────────────────────────────────────
# 1. 各表のデータ・件数
# ──────────────────────────────────────────────

df_daily_support_kpi = spark.table("gold.daily_support_kpi")
df_customer_support_risk = spark.table("gold.customer_support_risk")
df_category_support_summary = spark.table("gold.category_support_summary")
df_data_quality_summary = spark.table("gold.data_quality_summary")

print(f"\n=== gold.daily_support_kpi（全 {df_daily_support_kpi.count()} 件） ===")
display(df_daily_support_kpi)

print(f"\n=== gold.customer_support_risk（全 {df_customer_support_risk.count()} 件） ===")
display(df_customer_support_risk)

print(f"\n=== gold.category_support_summary（全 {df_category_support_summary.count()} 件） ===")
display(df_category_support_summary)

print(f"\n=== gold.data_quality_summary（全 {df_data_quality_summary.count()} 件） ===")
display(df_data_quality_summary)


# ──────────────────────────────────────────────
# 2. 各表の件数サマリ
# ──────────────────────────────────────────────

table_record_counts = spark.createDataFrame(
    [
        ("gold.daily_support_kpi", df_daily_support_kpi.count()),
        ("gold.customer_support_risk", df_customer_support_risk.count()),
        ("gold.category_support_summary", df_category_support_summary.count()),
        ("gold.data_quality_summary", df_data_quality_summary.count()),
    ],
    ["table_name", "record_count"],
)

print("\n=== Goldレイヤー 各表の件数サマリ ===")
display(table_record_counts)
