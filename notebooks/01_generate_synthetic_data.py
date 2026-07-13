# Databricks notebook source
# MAGIC %md
# MAGIC # Phase 2 — Synthetic Banking Data Generation
# MAGIC
# MAGIC Generates deterministic synthetic data for the customer retention demo
# MAGIC and writes it as Bronze Delta tables. See `CLAUDE.md` and
# MAGIC `docs/prompt-pack/PHASES_01_TO_04.md` (Phase 2) for the full spec, and
# MAGIC `docs/data-quality-report.md` for a report already computed from this
# MAGIC same generator outside Databricks (row counts, ranges, class balance,
# MAGIC intentional-pattern checks).
# MAGIC
# MAGIC **Do not call `SparkSession.builder` in this notebook.** `spark` is
# MAGIC auto-injected by the Databricks serverless/cluster runtime; calling
# MAGIC `SparkSession.builder` here previously caused an `INVALID_CONNECT_URL`
# MAGIC error in this exact workspace (see `legacy/ecommerce-sample/`, a prior
# MAGIC unrelated project that hit and fixed this).
# MAGIC
# MAGIC Rerunnable: every table is written with `mode("overwrite")`, so this
# MAGIC notebook can be run repeatedly without manual cleanup.

# COMMAND ----------

dbutils.widgets.text("catalog", "bank_demo", "Unity Catalog catalog name (used only if UC is enabled)")
dbutils.widgets.text("bronze_schema", "bronze", "Schema/database name for Bronze tables")
dbutils.widgets.text("num_customers", "8000", "Number of synthetic customers to generate")
dbutils.widgets.text("seed", "42", "Random seed (fixed for reproducibility)")

catalog = dbutils.widgets.get("catalog")
bronze_schema = dbutils.widgets.get("bronze_schema")
num_customers = int(dbutils.widgets.get("num_customers"))
seed = int(dbutils.widgets.get("seed"))

print(f"catalog={catalog} bronze_schema={bronze_schema} num_customers={num_customers} seed={seed}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Import the generator
# MAGIC
# MAGIC This notebook lives at `notebooks/01_generate_synthetic_data.py` in the
# MAGIC repo. `notebooks/lib/datagen.py` is a plain Python module with no Spark
# MAGIC dependency, unit-tested in `tests/test_datagen.py` outside Databricks.
# MAGIC Databricks Repos ("Files in Repos") set the notebook's own directory as
# MAGIC the working directory, so `lib` is importable as a sibling package.

# COMMAND ----------

import os
import sys

lib_dir = os.path.join(os.getcwd(), "lib")
if lib_dir not in sys.path:
    sys.path.append(lib_dir)

try:
    import datagen
except ImportError as exc:
    raise ImportError(
        "Could not import notebooks/lib/datagen.py. This notebook must be run "
        "from a Databricks Repo (Git folder) with the repository's folder "
        "structure intact, so 'notebooks/lib/datagen.py' sits next to this "
        "notebook. If this notebook was imported standalone, clone the full "
        "repo into a Databricks Repo instead."
    ) from exc

print(f"Loaded datagen module. Default SEED={datagen.SEED}, REFERENCE_DATE={datagen.REFERENCE_DATE}")

# COMMAND ----------

# MAGIC %md ## Generate synthetic rows (pure Python, deterministic)

# COMMAND ----------

tables = datagen.generate_all(num_customers, seed=seed)
for name, rows in tables.items():
    print(f"{name}: {len(rows):,} rows")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Detect Unity Catalog vs. Hive metastore
# MAGIC
# MAGIC This workspace's capabilities were **not** verified in advance — the
# MAGIC coding session that built this notebook had no network path to any
# MAGIC Databricks workspace. The cell below detects the correct mode live,
# MAGIC every time this notebook runs, instead of assuming one.

# COMMAND ----------

try:
    spark.sql(f"CREATE CATALOG IF NOT EXISTS {catalog}")
    spark.sql(f"USE CATALOG {catalog}")
    target_prefix = f"{catalog}.{bronze_schema}"
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {target_prefix}")
    print(f"Unity Catalog available. Writing to {target_prefix}.<table>")
except Exception as exc:
    target_prefix = f"{catalog}_{bronze_schema}"
    spark.sql(f"CREATE DATABASE IF NOT EXISTS {target_prefix}")
    print(
        f"Unity Catalog not available or not permitted here "
        f"({type(exc).__name__}: {exc}). Falling back to Hive metastore "
        f"database '{target_prefix}'. Writing to {target_prefix}.<table>"
    )

# COMMAND ----------

# MAGIC %md ## Convert to Spark DataFrames with explicit schemas and write Bronze Delta tables

# COMMAND ----------

from pyspark.sql.types import (
    DateType,
    DoubleType,
    IntegerType,
    StringType,
    StructField,
    StructType,
)

SCHEMAS = {
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

row_counts = {}
for table_name, rows in tables.items():
    df = spark.createDataFrame(rows, schema=SCHEMAS[table_name])
    (
        df.write.format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable(f"{target_prefix}.{table_name}")
    )
    row_counts[table_name] = spark.table(f"{target_prefix}.{table_name}").count()
    print(f"Wrote {target_prefix}.{table_name}: {row_counts[table_name]:,} rows")

# COMMAND ----------

# MAGIC %md ## Data-quality checks (run against the written Bronze tables)

# COMMAND ----------

print("=== Row counts ===")
for name, count in row_counts.items():
    print(f"  {name}: {count:,}")

print("\n=== Duplicate customer_id check ===")
dup_customers = (
    spark.table(f"{target_prefix}.customers").groupBy("customer_id").count().filter("count > 1").count()
)
print(f"  duplicate customer_id groups: {dup_customers}")
assert dup_customers == 0, "Found duplicate customer_id values in Bronze customers"

print("\n=== Null checks (customers) ===")
customers_df = spark.table(f"{target_prefix}.customers")
for field in SCHEMAS["customers"].fieldNames():
    n_nulls = customers_df.filter(f"{field} IS NULL").count()
    print(f"  {field}: {n_nulls} nulls")
    assert n_nulls == 0, f"Unexpected nulls in customers.{field}"

print("\n=== Referential integrity (sample: account_transactions -> customers) ===")
orphans = (
    spark.table(f"{target_prefix}.account_transactions")
    .select("customer_id")
    .distinct()
    .join(customers_df.select("customer_id"), "customer_id", "left_anti")
    .count()
)
print(f"  orphaned customer_id values in account_transactions: {orphans}")
assert orphans == 0, "account_transactions references unknown customer_id values"

print("\nAll Phase 2 data-quality checks passed.")

# COMMAND ----------

print(f"Bronze tables written under: {target_prefix}")
print("See docs/data-quality-report.md for row counts, ranges, class balance,")
print("and intentional-pattern checks computed from this same generator.")
