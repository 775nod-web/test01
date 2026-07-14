# Databricks notebook source
# MAGIC %md
# MAGIC # Phase 3 — Silver Layer and Customer 360
# MAGIC
# MAGIC Reads Bronze tables written by `01_generate_synthetic_data.py`,
# MAGIC builds cleaned Silver tables per domain, and builds the mandatory Gold
# MAGIC `customer_360` table. See `CLAUDE.md` and
# MAGIC `docs/prompt-pack/PHASES_01_TO_04.md` (Phase 3) for the full spec, and
# MAGIC `docs/data-dictionary.md` for column definitions.
# MAGIC
# MAGIC "30-day" and "90-day" changes are approximated as month-over-month and
# MAGIC 3-months-over-3-months comparisons, since Phase 2 aggregates activity
# MAGIC monthly rather than daily (documented in `docs/free-edition-limitations.md`).
# MAGIC
# MAGIC Rerunnable: every table is `CREATE OR REPLACE`, so this notebook can be
# MAGIC run repeatedly without manual cleanup. Run `01_generate_synthetic_data.py`
# MAGIC first in the same session/cluster.

# COMMAND ----------

dbutils.widgets.text("catalog", "bank_demo", "Unity Catalog catalog name (used only if UC is enabled)")
dbutils.widgets.text("bronze_schema", "bronze", "Schema/database name for Bronze tables")
dbutils.widgets.text("silver_schema", "silver", "Schema/database name for Silver tables")
dbutils.widgets.text("gold_schema", "gold", "Schema/database name for Gold tables")

catalog = dbutils.widgets.get("catalog")
bronze_schema = dbutils.widgets.get("bronze_schema")
silver_schema = dbutils.widgets.get("silver_schema")
gold_schema = dbutils.widgets.get("gold_schema")

# COMMAND ----------

import os
import sys

lib_dir = os.path.join(os.getcwd(), "lib")
if lib_dir not in sys.path:
    sys.path.append(lib_dir)

try:
    from catalog_utils import resolve_schema_prefix
except ImportError as exc:
    raise ImportError(
        "Could not import notebooks/lib/catalog_utils.py. Run this notebook "
        "from a Databricks Repo (Git folder) with the repository's folder "
        "structure intact."
    ) from exc

bronze_prefix = resolve_schema_prefix(spark, catalog, bronze_schema)
silver_prefix = resolve_schema_prefix(spark, catalog, silver_schema)
gold_prefix = resolve_schema_prefix(spark, catalog, gold_schema)

print(f"bronze={bronze_prefix} silver={silver_prefix} gold={gold_prefix}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Run Silver transformations
# MAGIC
# MAGIC SQL files live in `sql/silver/*.sql` as repo-relative paths so they can
# MAGIC be reviewed and version-controlled independently of this notebook.
# MAGIC They use `{bronze}`/`{silver}` placeholders substituted below.

# COMMAND ----------

REPO_ROOT = os.path.dirname(os.getcwd())  # notebooks/ -> repo root
SQL_SILVER_DIR = os.path.join(REPO_ROOT, "sql", "silver")
SQL_GOLD_DIR = os.path.join(REPO_ROOT, "sql", "gold")

SILVER_SCRIPTS = [
    "01_customers.sql",
    "02_account_transactions.sql",
    "03_card_usage.sql",
    "04_app_activity.sql",
    "05_contact_history.sql",
    "06_product_holdings.sql",
    "07_campaign_history.sql",
]


def run_sql_file(path: str, **placeholders) -> None:
    with open(path) as f:
        sql_text = f.read()
    for key, value in placeholders.items():
        sql_text = sql_text.replace(f"{{{key}}}", value)
    for statement in sql_text.split(";"):
        statement = statement.strip()
        if statement:
            spark.sql(statement)


for script in SILVER_SCRIPTS:
    path = os.path.join(SQL_SILVER_DIR, script)
    run_sql_file(path, bronze=bronze_prefix, silver=silver_prefix)
    table_name = script.split("_", 1)[1].replace(".sql", "")
    count = spark.table(f"{silver_prefix}.{table_name}").count()
    print(f"Built {silver_prefix}.{table_name}: {count:,} rows")

# COMMAND ----------

# MAGIC %md ## Build Gold `customer_360`

# COMMAND ----------

run_sql_file(
    os.path.join(SQL_GOLD_DIR, "customer_360.sql"),
    bronze=bronze_prefix,
    silver=silver_prefix,
    gold=gold_prefix,
)
customer_360_count = spark.table(f"{gold_prefix}.customer_360").count()
print(f"Built {gold_prefix}.customer_360: {customer_360_count:,} rows")

# COMMAND ----------

# MAGIC %md ## Reconciliation checks

# COMMAND ----------

silver_customer_count = spark.table(f"{silver_prefix}.customers").filter(
    "data_quality_status = 'valid'"
).count()
print(f"silver.customers (valid): {silver_customer_count:,}")
print(f"gold.customer_360: {customer_360_count:,}")
assert customer_360_count == silver_customer_count, (
    "customer_360 row count does not match valid Silver customer count "
    "(expected exactly one row per customer)"
)

dup_check = (
    spark.table(f"{gold_prefix}.customer_360")
    .groupBy("customer_id").count().filter("count > 1").count()
)
print(f"duplicate customer_id in customer_360: {dup_check}")
assert dup_check == 0

negative_balance_check = spark.table(f"{gold_prefix}.customer_360").filter(
    "current_balance < 0"
).count()
print(f"customers with negative current_balance: {negative_balance_check}")
assert negative_balance_check == 0, "Unexpected negative balances in customer_360"

null_value_segment = spark.table(f"{gold_prefix}.customer_360").filter(
    "value_segment IS NULL"
).count()
print(f"customers with null value_segment: {null_value_segment}")
assert null_value_segment == 0

print("\nAll Phase 3 reconciliation checks passed.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Representative customer profiles for the demo
# MAGIC
# MAGIC Selected programmatically (not hand-picked) so they are reproducible
# MAGIC with the fixed seed. See `docs/representative-customers.md` for the
# MAGIC customer IDs and a written summary of each story.

# COMMAND ----------

spark.sql(
    f"""
    SELECT customer_id, value_segment, current_balance, balance_change_90d_pct,
           card_spend_change_90d_pct, login_change_90d_pct, complaint_count_90d,
           unresolved_contacts_total, salary_deposit_stopped_flag
    FROM {gold_prefix}.customer_360
    WHERE value_segment = 'High' AND balance_change_90d_pct < -0.30
    ORDER BY balance_change_90d_pct ASC
    LIMIT 5
    """
).show(truncate=False)

spark.sql(
    f"""
    SELECT customer_id, value_segment, card_spend_change_90d_pct, login_change_90d_pct
    FROM {gold_prefix}.customer_360
    WHERE card_spend_change_90d_pct < -0.30 AND login_change_90d_pct < -0.50
    ORDER BY login_change_90d_pct ASC
    LIMIT 5
    """
).show(truncate=False)

spark.sql(
    f"""
    SELECT customer_id, value_segment, complaint_count_90d, unresolved_contacts_total
    FROM {gold_prefix}.customer_360
    WHERE complaint_count_90d >= 2 AND unresolved_contacts_total >= 1
    ORDER BY complaint_count_90d DESC
    LIMIT 5
    """
).show(truncate=False)
