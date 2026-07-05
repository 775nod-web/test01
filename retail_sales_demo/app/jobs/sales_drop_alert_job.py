"""売上急減しきい値アラート バッチ（追加機能・優先度高）。

Databricks Jobsのノートブック/Pythonタスクとして日次実行する想定。
gold_daily_store_sales から店舗別の前日比売上変化率を算出し、
しきい値（デフォルト-20%）を超えた店舗を gold_sales_alerts に書き出す。

実ワークスペースで確認済み: Gold layerは workspace.gold。
サンプルデータは店舗ごとに売上のある日が飛び飛びのため、本ジョブでは
「前日」ではなく「直近の売上記録日」との比較で変化率を算出する。
"""
import os

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window

CATALOG = os.environ.get("GOLD_CATALOG", "workspace")
SCHEMA = os.environ.get("GOLD_SCHEMA", "gold")
THRESHOLD_PCT = float(os.environ.get("SALES_DROP_ALERT_THRESHOLD_PCT", "-20"))


def main() -> None:
    spark = SparkSession.builder.getOrCreate()

    daily_sales = spark.table(f"{CATALOG}.{SCHEMA}.gold_daily_store_sales")

    window = Window.partitionBy("store_id").orderBy("sales_date")
    with_prev = daily_sales.withColumn(
        "prev_sales_amount", F.lag("total_sales_amount").over(window)
    )

    changed = with_prev.withColumn(
        "sales_change_pct",
        F.when(
            F.col("prev_sales_amount").isNotNull() & (F.col("prev_sales_amount") != 0),
            (F.col("total_sales_amount") - F.col("prev_sales_amount")) / F.col("prev_sales_amount") * 100.0,
        ),
    )

    alerts = (
        changed.filter(F.col("sales_change_pct") <= THRESHOLD_PCT)
        .select(
            F.col("sales_date").alias("alert_date"),
            "store_id",
            "store_name",
            "sales_change_pct",
            F.lit(THRESHOLD_PCT).alias("threshold_pct"),
            F.concat(
                F.col("store_name"),
                F.lit(" の売上が前日比 "),
                F.round(F.col("sales_change_pct"), 1).cast("string"),
                F.lit("% 減少しました"),
            ).alias("message"),
        )
    )

    alerts.write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.gold_sales_alerts")


if __name__ == "__main__":
    main()
