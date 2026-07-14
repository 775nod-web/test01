"""
DEV-ONLY utility: generates a small local Parquet snapshot of the Gold and
Silver tables under backend/local_fixtures/, using a local Spark+Delta
session and the exact same sql/silver/*.sql, sql/gold/*.sql files used in
Databricks. This is what backend/db.py's local fallback engine reads when
Databricks env vars are not configured, so the app can be developed and
demoed locally without a Databricks workspace connection.

Not part of the deployed Databricks App — the deployed app always queries
Databricks SQL directly (see backend/db.py). Rerun this script after any
change to the generator or SQL files to refresh the local fixtures:

    pip install -r requirements-dev.txt
    python scripts/generate_local_fixtures.py
"""

import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "notebooks" / "lib"))
import datagen  # noqa: E402

from delta import configure_spark_with_delta_pip  # noqa: E402
from pyspark.sql import SparkSession  # noqa: E402
from pyspark.sql.types import (  # noqa: E402
    DateType,
    DoubleType,
    IntegerType,
    StringType,
    StructField,
    StructType,
)

NUM_CUSTOMERS = 1200
SEED = datagen.SEED
OUT_DIR = REPO_ROOT / "backend" / "local_fixtures"

BRONZE_SCHEMAS = {
    "customers": StructType(
        [
            StructField("customer_id", StringType(), False),
            StructField("signup_date", DateType(), False),
            StructField("tenure_months", IntegerType(), False),
            StructField("age_band", StringType(), False),
            StructField("acquisition_channel", StringType(), False),
            StructField("home_region", StringType(), False),
            StructField("customer_value_segment", StringType(), False),
            StructField("simulated_annual_value", DoubleType(), False),
            StructField("churn_label_90d", IntegerType(), False),
        ]
    ),
    "account_transactions": StructType(
        [
            StructField("customer_id", StringType(), False),
            StructField("activity_month", DateType(), False),
            StructField("avg_daily_balance", DoubleType(), False),
            StructField("eom_balance", DoubleType(), False),
            StructField("deposit_count", IntegerType(), False),
            StructField("withdrawal_count", IntegerType(), False),
            StructField("transfer_out_amount", DoubleType(), False),
            StructField("salary_deposit_flag", IntegerType(), False),
            StructField("total_transaction_amount", DoubleType(), False),
        ]
    ),
    "card_usage": StructType(
        [
            StructField("customer_id", StringType(), False),
            StructField("activity_month", DateType(), False),
            StructField("card_spend_amount", DoubleType(), False),
            StructField("card_txn_count", IntegerType(), False),
            StructField("declined_txn_count", IntegerType(), False),
            StructField("card_active_flag", IntegerType(), False),
        ]
    ),
    "app_activity": StructType(
        [
            StructField("customer_id", StringType(), False),
            StructField("activity_month", DateType(), False),
            StructField("login_count", IntegerType(), False),
            StructField("session_count", IntegerType(), False),
            StructField("avg_session_minutes", DoubleType(), False),
            StructField("days_since_last_login_eom", IntegerType(), False),
        ]
    ),
    "contact_history": StructType(
        [
            StructField("contact_id", StringType(), False),
            StructField("customer_id", StringType(), False),
            StructField("contact_date", DateType(), False),
            StructField("channel", StringType(), False),
            StructField("reason", StringType(), False),
            StructField("is_complaint", IntegerType(), False),
            StructField("is_resolved", IntegerType(), False),
            StructField("satisfaction_score", IntegerType(), False),
        ]
    ),
    "product_holdings": StructType(
        [
            StructField("customer_id", StringType(), False),
            StructField("activity_month", DateType(), False),
            StructField("product_count", IntegerType(), False),
            StructField("has_checking", IntegerType(), False),
            StructField("has_savings", IntegerType(), False),
            StructField("has_credit_card", IntegerType(), False),
            StructField("has_loan", IntegerType(), False),
            StructField("has_investment", IntegerType(), False),
        ]
    ),
    "campaign_history": StructType(
        [
            StructField("campaign_id", StringType(), False),
            StructField("customer_id", StringType(), False),
            StructField("campaign_date", DateType(), False),
            StructField("campaign_type", StringType(), False),
            StructField("channel", StringType(), False),
            StructField("responded_flag", IntegerType(), False),
            StructField("converted_flag", IntegerType(), False),
        ]
    ),
}


def run_sql_file(spark, path, **placeholders):
    sql_text = path.read_text()
    for key, value in placeholders.items():
        sql_text = sql_text.replace(f"{{{key}}}", value)
    for statement in sql_text.split(";"):
        statement = statement.strip()
        if statement:
            spark.sql(statement)


def main():
    warehouse = str(REPO_ROOT / ".local_spark_warehouse_tmp")
    builder = (
        SparkSession.builder.appName("generate_local_fixtures")
        .master("local[2]")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        .config("spark.sql.warehouse.dir", warehouse)
    )
    spark = configure_spark_with_delta_pip(builder).getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")

    tables = datagen.generate_all(NUM_CUSTOMERS, seed=SEED)
    bronze, silver, gold = "fixture_bronze", "fixture_silver", "fixture_gold"
    for db in (bronze, silver, gold):
        spark.sql(f"CREATE DATABASE IF NOT EXISTS {db}")

    for table_name, rows in tables.items():
        df = spark.createDataFrame(rows, schema=BRONZE_SCHEMAS[table_name])
        df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(
            f"{bronze}.{table_name}"
        )

    silver_dir = REPO_ROOT / "sql" / "silver"
    for script in [
        "01_customers.sql",
        "02_account_transactions.sql",
        "03_card_usage.sql",
        "04_app_activity.sql",
        "05_contact_history.sql",
        "06_product_holdings.sql",
        "07_campaign_history.sql",
    ]:
        run_sql_file(spark, silver_dir / script, bronze=bronze, silver=silver)

    gold_dir = REPO_ROOT / "sql" / "gold"
    run_sql_file(spark, gold_dir / "customer_360.sql", bronze=bronze, silver=silver, gold=gold)
    run_sql_file(spark, gold_dir / "retention_action_list.sql", gold=gold)
    run_sql_file(spark, gold_dir / "executive_kpis.sql", gold=gold)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    exports = [
        (f"{gold}.customer_360", "gold_customer_360.parquet"),
        (f"{gold}.retention_action_list", "gold_retention_action_list.parquet"),
        (f"{gold}.executive_kpis", "gold_executive_kpis.parquet"),
        (f"{silver}.account_transactions", "silver_account_transactions.parquet"),
        (f"{silver}.card_usage", "silver_card_usage.parquet"),
        (f"{silver}.app_activity", "silver_app_activity.parquet"),
        (f"{silver}.product_holdings", "silver_product_holdings.parquet"),
        (f"{silver}.contact_history", "silver_contact_history.parquet"),
    ]
    for table, filename in exports:
        df = spark.table(table).coalesce(1)
        out_path = OUT_DIR / filename
        tmp_dir = OUT_DIR / f"_tmp_{filename}"
        df.write.mode("overwrite").parquet(str(tmp_dir))
        part_file = next(tmp_dir.glob("part-*.parquet"))
        shutil.move(str(part_file), str(out_path))
        shutil.rmtree(tmp_dir)
        print(f"Wrote {out_path} ({spark.table(table).count():,} rows)")

    spark.stop()
    shutil.rmtree(warehouse, ignore_errors=True)
    shutil.rmtree(REPO_ROOT / "metastore_db", ignore_errors=True)
    derby_log = REPO_ROOT / "derby.log"
    if derby_log.exists():
        derby_log.unlink()
    print("\nLocal fixtures generated successfully.")


if __name__ == "__main__":
    main()
