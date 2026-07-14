# Databricks notebook source
# MAGIC %md
# MAGIC # Phase 4 — Risk Scoring and Retention Actions
# MAGIC
# MAGIC Reads Gold `customer_360` (Phase 3) and builds `retention_action_list`
# MAGIC and `executive_kpis`. See `CLAUDE.md` §10–11 and
# MAGIC `docs/prompt-pack/PHASES_01_TO_04.md` (Phase 4) for the full spec, and
# MAGIC `docs/risk-scoring.md` for the scoring rule and action-mapping table.
# MAGIC
# MAGIC This is a **transparent, configurable point score** — not a predictive
# MAGIC model — and every recommended action requires human review before any
# MAGIC customer outreach (CLAUDE.md §11).
# MAGIC
# MAGIC Rerunnable: every table is rebuilt with `DROP TABLE IF EXISTS` +
# MAGIC `CREATE TABLE ... AS SELECT`. Run `01_generate_synthetic_data.py` then
# MAGIC `02_build_silver_and_gold.py` first in the same session/cluster.

# COMMAND ----------

dbutils.widgets.text("catalog", "bank_demo", "Unity Catalog catalog name (used only if UC is enabled)")
dbutils.widgets.text("gold_schema", "gold", "Schema/database name for Gold tables")

catalog = dbutils.widgets.get("catalog")
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

gold_prefix = resolve_schema_prefix(spark, catalog, gold_schema)
print(f"gold={gold_prefix}")

# COMMAND ----------

REPO_ROOT = os.path.dirname(os.getcwd())
SQL_GOLD_DIR = os.path.join(REPO_ROOT, "sql", "gold")


def run_sql_file(path: str, **placeholders) -> None:
    with open(path) as f:
        sql_text = f.read()
    for key, value in placeholders.items():
        sql_text = sql_text.replace(f"{{{key}}}", value)
    for statement in sql_text.split(";"):
        statement = statement.strip()
        if statement:
            spark.sql(statement)

# COMMAND ----------

# MAGIC %md ## Build `retention_action_list`

# COMMAND ----------

run_sql_file(os.path.join(SQL_GOLD_DIR, "retention_action_list.sql"), gold=gold_prefix)
action_list_count = spark.table(f"{gold_prefix}.retention_action_list").count()
print(f"Built {gold_prefix}.retention_action_list: {action_list_count:,} rows")

# COMMAND ----------

# MAGIC %md ## Build `executive_kpis`

# COMMAND ----------

run_sql_file(os.path.join(SQL_GOLD_DIR, "executive_kpis.sql"), gold=gold_prefix)
spark.table(f"{gold_prefix}.executive_kpis").show(truncate=False)

# COMMAND ----------

# MAGIC %md ## Quality gate checks

# COMMAND ----------

customer_360_count = spark.table(f"{gold_prefix}.customer_360").count()
print(f"customer_360: {customer_360_count:,}  retention_action_list: {action_list_count:,}")
assert action_list_count == customer_360_count, "retention_action_list must have one row per customer"

no_driver_high_risk = spark.sql(
    f"""
    SELECT COUNT(*) AS n FROM {gold_prefix}.retention_action_list
    WHERE risk_segment IN ('High', 'Medium') AND primary_driver = 'No material risk driver'
    """
).collect()[0]["n"]
print(f"High/Medium risk rows with no explainable driver: {no_driver_high_risk}")
assert no_driver_high_risk == 0, "Every High/Medium risk customer must have an explainable primary driver"

no_action_review_flag = spark.sql(
    f"""
    SELECT COUNT(*) AS n FROM {gold_prefix}.retention_action_list
    WHERE recommended_action != 'No immediate action' AND human_review_required = 0
    """
).collect()[0]["n"]
print(f"Recommended actions missing human_review_required: {no_action_review_flag}")
assert no_action_review_flag == 0

kpi_row = spark.table(f"{gold_prefix}.executive_kpis").collect()[0]
assert kpi_row["total_customers"] == customer_360_count
assert (
    kpi_row["high_risk_customers"] + kpi_row["medium_risk_customers"] + kpi_row["low_risk_customers"]
    == kpi_row["total_customers"]
), "risk segment counts must reconcile to total_customers"

# high risk must not be dominated by high-value customers only (risk and value are independent)
value_mix = spark.sql(
    f"""
    SELECT value_segment, COUNT(*) AS n
    FROM {gold_prefix}.retention_action_list
    WHERE risk_segment = 'High'
    GROUP BY value_segment
    """
).collect()
print("High-risk population by value segment:", {r["value_segment"]: r["n"] for r in value_mix})
assert len(value_mix) > 1, "High risk should not be a single value segment only"

print("\nAll Phase 4 quality gate checks passed.")

# COMMAND ----------

# MAGIC %md ## Broad vs. prioritized audience (for the Executive Overview page)

# COMMAND ----------

spark.sql(
    f"""
    SELECT broad_campaign_audience_count, prioritized_audience_count,
           ROUND(100.0 * prioritized_audience_count / broad_campaign_audience_count, 1) AS prioritized_pct
    FROM {gold_prefix}.executive_kpis
    """
).show(truncate=False)
