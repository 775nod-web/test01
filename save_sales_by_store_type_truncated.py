# Databricks ノートブック用
# 「過去1ヶ月・店舗タイプ別 売上金額集計」を小数点切り捨てした状態で
# Delta テーブルとして保存する（Databricks Free Edition / Hiveメタストア）
#
# 前提：aggregate_sales_by_store_type.py を実行済みで、
#       df_sales_by_store_type（同セッション内のDataFrame）が存在すること

from pyspark.sql import functions as F

df_sales_by_store_type_truncated = (
    df_sales_by_store_type
    .withColumn("total_sales_amount", F.floor(F.col("total_sales_amount")))  # 小数点以下切り捨て
)

# ──────────────────────────────────────────────
# Delta テーブルとして保存
# ──────────────────────────────────────────────

spark.sql("CREATE DATABASE IF NOT EXISTS retail")

(
    df_sales_by_store_type_truncated
    .write
    .format("delta")                        # Delta Lake 形式で保存
    .mode("overwrite")                      # 既存テーブルを上書き（冪等実行を保証）
    .option("overwriteSchema", "true")      # スキーマ変更も上書き許可
    .saveAsTable("retail.sales_by_store_type_monthly")
)

print("retail.sales_by_store_type_monthly の保存が完了しました")
display(spark.table("retail.sales_by_store_type_monthly"))
