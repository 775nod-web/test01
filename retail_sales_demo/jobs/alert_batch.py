"""Phase 3-D: daily store sales drop alert batch.

Computes day-over-day (DoD) and week-over-week (WoW) % change in net_sales
per store from gold_daily_store_sales, and writes rows that breach
THRESHOLD_PCT into gold_store_sales_alerts. GET /api/alerts (app/backend/main.py)
reads the latest day's rows from that table — this script is the only writer.

Runs as a Databricks Jobs Python task (see resources/alert_batch_job.json),
with `spark` provided by the job's runtime — it is NOT executed by the
FastAPI backend.

*** NOT RUN OR VERIFIED ***: this coding session has no network access to
the Databricks workspace, so this script has never been executed against
real data, and gold_daily_store_sales's real column names were never
confirmed (see app/backend/schema_assumptions.py for the same assumption
this script makes: sales_date, store_id, store_name, net_sales). Before
deploying, run this against a dev/test schema first.
"""
from pyspark.sql import SparkSession, functions as F
from pyspark.sql.window import Window

GOLD_CATALOG = "workspace"
GOLD_SCHEMA = "gold"
DAILY_STORE_SALES_TABLE = f"{GOLD_CATALOG}.{GOLD_SCHEMA}.gold_daily_store_sales"
ALERTS_TABLE = f"{GOLD_CATALOG}.{GOLD_SCHEMA}.gold_store_sales_alerts"

THRESHOLD_PCT = -20.0  # trigger when net_sales drops by this % or more


def _pct_change(current_col: str, previous_col: str):
    return F.when(
        F.col(previous_col).isNull() | (F.col(previous_col) == 0), F.lit(None)
    ).otherwise((F.col(current_col) - F.col(previous_col)) / F.col(previous_col) * 100)


def main() -> None:
    spark = SparkSession.builder.getOrCreate()

    spark.sql(
        f"""
        CREATE TABLE IF NOT EXISTS {ALERTS_TABLE} (
            alert_date DATE,
            store_id STRING,
            store_name STRING,
            comparison_type STRING,
            current_value DOUBLE,
            previous_value DOUBLE,
            pct_change DOUBLE,
            threshold_pct DOUBLE,
            triggered_at TIMESTAMP
        ) USING DELTA
        """
    )

    daily = spark.table(DAILY_STORE_SALES_TABLE).select("sales_date", "store_id", "store_name", "net_sales")

    by_store = Window.partitionBy("store_id").orderBy("sales_date")
    with_lags = daily.withColumn("prev_day_sales", F.lag("net_sales", 1).over(by_store)).withColumn(
        "prev_week_sales", F.lag("net_sales", 7).over(by_store)
    )

    latest_date = daily.agg(F.max("sales_date").alias("d")).collect()[0]["d"]
    if latest_date is None:
        print("[alert_batch] gold_daily_store_sales is empty; nothing to do.")
        return
    latest = with_lags.filter(F.col("sales_date") == F.lit(latest_date))

    dod = (
        latest.withColumn("comparison_type", F.lit("DoD"))
        .withColumn("current_value", F.col("net_sales"))
        .withColumn("previous_value", F.col("prev_day_sales"))
        .withColumn("pct_change", _pct_change("net_sales", "prev_day_sales"))
    )
    wow = (
        latest.withColumn("comparison_type", F.lit("WoW"))
        .withColumn("current_value", F.col("net_sales"))
        .withColumn("previous_value", F.col("prev_week_sales"))
        .withColumn("pct_change", _pct_change("net_sales", "prev_week_sales"))
    )

    alerts = (
        dod.unionByName(wow)
        .filter(F.col("pct_change").isNotNull() & (F.col("pct_change") <= THRESHOLD_PCT))
        .select(
            F.col("sales_date").alias("alert_date"),
            "store_id",
            "store_name",
            "comparison_type",
            "current_value",
            "previous_value",
            "pct_change",
            F.lit(THRESHOLD_PCT).alias("threshold_pct"),
            F.current_timestamp().alias("triggered_at"),
        )
    )

    # Idempotent re-runs: replace today's alerts rather than accumulating duplicates.
    spark.sql(f"DELETE FROM {ALERTS_TABLE} WHERE alert_date = '{latest_date}'")
    alerts.write.mode("append").format("delta").saveAsTable(ALERTS_TABLE)

    print(f"[alert_batch] alert_date={latest_date} triggered_alerts={alerts.count()} threshold_pct={THRESHOLD_PCT}")


if __name__ == "__main__":
    main()
