"""売上急減しきい値アラート バッチ（追加機能・優先度高）。

Databricks Jobsのノートブック/Pythonタスクとして日次実行する想定。
gold_daily_store_sales から店舗別の前日比売上変化率を算出し、
しきい値（デフォルト-20%）を超えた店舗を gold_sales_alerts に書き出す。

実ワークスペースで確認済み: Gold layerは workspace.gold。
サンプルデータは店舗ごとに売上のある日が飛び飛び（年間366日中40日程度）のため、
本ジョブでは「前日」ではなく「直近の売上記録日」との比較で変化率を算出する。

実データでの検証で判明した2つの問題への対応:
1. 記録日同士が数週間離れているケースで比較すると、文脈の異なる日を比べることになり
   ノイズの多いアラートが大量発生した（200件中90件がアラート対象になった）。
   → 直近の記録日との間隔が14日を超える場合は比較対象から除外する。
2. sales_change_pctが-100%を下回る（理論上あり得ない）ケースが発生した。
   これは売上金額がマイナスになっている取引データが存在することを示唆しており、
   売上急減アラートではなくデータ品質側の問題として扱うべきである。
   → 本ジョブでは-100%未満のケースを対象外とし、原因調査は別途Silver/Gold層で行う。
"""
import os

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window

CATALOG = os.environ.get("GOLD_CATALOG", "workspace")
SCHEMA = os.environ.get("GOLD_SCHEMA", "gold")
THRESHOLD_PCT = float(os.environ.get("SALES_DROP_ALERT_THRESHOLD_PCT", "-20"))
MAX_COMPARISON_GAP_DAYS = int(os.environ.get("SALES_DROP_ALERT_MAX_GAP_DAYS", "14"))


def main() -> None:
    spark = SparkSession.builder.getOrCreate()

    daily_sales = spark.table(f"{CATALOG}.{SCHEMA}.gold_daily_store_sales")

    window = Window.partitionBy("store_id").orderBy("sales_date")
    with_prev = daily_sales.withColumn(
        "prev_sales_amount", F.lag("total_sales_amount").over(window)
    ).withColumn(
        "prev_sales_date", F.lag("sales_date").over(window)
    )

    changed = with_prev.withColumn(
        "days_since_prev", F.datediff(F.col("sales_date"), F.col("prev_sales_date"))
    ).withColumn(
        "sales_change_pct",
        F.when(
            F.col("prev_sales_amount").isNotNull() & (F.col("prev_sales_amount") != 0),
            (F.col("total_sales_amount") - F.col("prev_sales_amount")) / F.col("prev_sales_amount") * 100.0,
        ),
    )

    alerts = (
        changed.filter(
            (F.col("sales_change_pct") <= THRESHOLD_PCT)
            & (F.col("sales_change_pct") >= -100)
            & (F.col("days_since_prev") <= MAX_COMPARISON_GAP_DAYS)
        )
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
