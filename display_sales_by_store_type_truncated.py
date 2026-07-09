# Databricks ノートブック用
# 「過去1ヶ月・店舗タイプ別 売上金額集計」の小数点を切り捨てた状態で表示を確認する
#
# 前提：aggregate_sales_by_store_type.py を実行済みで、
#       df_sales_by_store_type（同セッション内のDataFrame）が存在すること

from pyspark.sql import functions as F

df_sales_by_store_type_truncated = (
    df_sales_by_store_type
    .withColumn("total_sales_amount", F.floor(F.col("total_sales_amount")))  # 小数点以下切り捨て
)

print("=== 過去1ヶ月・店舗タイプ別 売上金額集計（小数点切り捨て） ===")
display(df_sales_by_store_type_truncated)
