# Databricks ノートブック用
# fact_sales_transactions（ファクトテーブル）と dim_store（ディメンションテーブル）を結合し、
# 過去1ヶ月分の店舗タイプ別売上金額を集計する
#
# 前提：create_fact_sales_table.py / create_dim_store_table.py を実行済みで、
#       retail.fact_sales_transactions / retail.dim_store が保存されていること

from pyspark.sql import functions as F

df_fact_sales = spark.table("retail.fact_sales_transactions")
df_dim_store  = spark.table("retail.dim_store")


# ──────────────────────────────────────────────
# 1. ファクトテーブルとディメンションテーブルの結合
# ──────────────────────────────────────────────

df_sales_with_store = (
    df_fact_sales
    .join(df_dim_store, on="store_id", how="inner")   # store_id をキーに店舗属性を付与
)


# ──────────────────────────────────────────────
# 2. 過去1ヶ月・店舗タイプ別の売上金額集計
# ──────────────────────────────────────────────

df_sales_by_store_type = (
    df_sales_with_store
    .filter(F.col("transaction_datetime") >= F.date_sub(F.current_date(), 30))  # 過去1ヶ月分に絞り込み
    .groupBy("store_type")
    .agg(F.sum("sales_amount").alias("total_sales_amount"))
    .orderBy(F.col("total_sales_amount").desc())
)


# ──────────────────────────────────────────────
# 3. Databricksノートブック上での結果表示
# ──────────────────────────────────────────────

print(f"=== 結合結果（{df_sales_with_store.count():,}件） ===")
display(df_sales_with_store)

print("=== 過去1ヶ月・店舗タイプ別 売上金額集計 ===")
display(df_sales_by_store_type)
