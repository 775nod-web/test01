# Databricks ノートブック用
# fact_sales_transactions（ファクトテーブル）と dim_store（ディメンションテーブル）を表示する
#
# 前提：create_fact_sales_table.py / create_dim_store_table.py を実行済みで、
#       retail.fact_sales_transactions / retail.dim_store が保存されていること

# ──────────────────────────────────────────────
# 1. ファクトテーブル（売上テーブル）の表示
# ──────────────────────────────────────────────

df_fact_sales = spark.table("retail.fact_sales_transactions")

print(f"=== retail.fact_sales_transactions（{df_fact_sales.count():,}件） ===")
display(df_fact_sales)  # Databricksノートブックの表形式表示（見やすいUI）

# ノートブック以外（.py実行時など）で確認する場合は以下も利用可能
# df_fact_sales.show(10, truncate=False)


# ──────────────────────────────────────────────
# 2. ディメンションテーブル（店舗テーブル）の表示
# ──────────────────────────────────────────────

df_dim_store = spark.table("retail.dim_store")

print(f"=== retail.dim_store（{df_dim_store.count()}件） ===")
display(df_dim_store)  # Databricksノートブックの表形式表示（見やすいUI）

# df_dim_store.show(10, truncate=False)
