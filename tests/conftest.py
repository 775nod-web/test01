"""
Shared local Spark+Delta fixtures for tests that validate real SQL files
(sql/silver, sql/gold, sql/queries) against real generator output. Nothing
here touches Databricks — these fixtures build a local Bronze/Silver/Gold
pipeline from notebooks/lib/datagen.py so the actual SQL can be exercised
without a workspace connection.

Requires pyspark + delta-spark, which are NOT in requirements.txt (the
FastAPI backend queries Databricks SQL directly; it never runs Spark
itself). Install separately to run these tests:
    pip install pyspark==3.5.3 delta-spark==3.2.1

Importing pyspark is deferred and defensive: a module-level
pytest.importorskip() here would abort collection for the WHOLE test
session (including tests/test_datagen.py, which needs neither) rather than
just skipping the tests that use these fixtures. The `spark` fixture below
is what actually skips, via importorskip inside the fixture itself.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "notebooks" / "lib"))
import datagen  # noqa: E402

NUM_CUSTOMERS = 500
SEED = datagen.SEED


def _bronze_schemas():
    from pyspark.sql.types import (
        DateType,
        DoubleType,
        IntegerType,
        StringType,
        StructField,
        StructType,
    )

    return {
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


@pytest.fixture(scope="session")
def spark(tmp_path_factory):
    pytest.importorskip("pyspark")
    pytest.importorskip("delta")
    from delta import configure_spark_with_delta_pip
    from pyspark.sql import SparkSession

    warehouse = str(tmp_path_factory.mktemp("spark-warehouse"))
    builder = (
        SparkSession.builder.appName("test_bank_demo")
        .master("local[2]")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        .config("spark.sql.warehouse.dir", warehouse)
        # Databricks runs with ANSI SQL mode on by default (local OSS Spark
        # defaults to off) — matching it here is what catches bugs like
        # `arr[0]` throwing INVALID_ARRAY_INDEX on an empty array instead of
        # returning NULL, which only surfaces in a real Databricks workspace
        # otherwise. Use get()/try_element_at() for safe indexing.
        .config("spark.sql.ansi.enabled", "true")
    )
    session = configure_spark_with_delta_pip(builder).getOrCreate()
    session.sparkContext.setLogLevel("ERROR")
    yield session
    session.stop()


@pytest.fixture(scope="session")
def bronze_silver_gold(spark):
    """Builds real Bronze -> Silver -> Gold customer_360 from the actual
    generator and SQL files, at a smaller scale for test speed. Returns
    (bronze, silver, gold) database names. Session-scoped so every test
    module in this run shares one build."""
    tables = datagen.generate_all(NUM_CUSTOMERS, seed=SEED)
    bronze, silver, gold = "test_bronze", "test_silver", "test_gold"
    for db in (bronze, silver, gold):
        spark.sql(f"CREATE DATABASE IF NOT EXISTS {db}")

    schemas = _bronze_schemas()
    for table_name, rows in tables.items():
        df = spark.createDataFrame(rows, schema=schemas[table_name])
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

    run_sql_file(spark, REPO_ROOT / "sql" / "gold" / "customer_360.sql", bronze=bronze, silver=silver, gold=gold)
    run_sql_file(spark, REPO_ROOT / "sql" / "gold" / "retention_action_list.sql", gold=gold)
    run_sql_file(spark, REPO_ROOT / "sql" / "gold" / "executive_kpis.sql", gold=gold)
    return bronze, silver, gold


@pytest.fixture(scope="session")
def customer_360_table(bronze_silver_gold):
    return bronze_silver_gold[2]


@pytest.fixture(scope="session")
def retention_action_list(bronze_silver_gold):
    return bronze_silver_gold[2]
