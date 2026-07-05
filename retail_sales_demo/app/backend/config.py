import os

GOLD_CATALOG = os.environ.get("GOLD_CATALOG", "workspace")
GOLD_SCHEMA = os.environ.get("GOLD_SCHEMA", "gold")
SILVER_SCHEMA = os.environ.get("SILVER_SCHEMA", "silver")

# Databricks Apps injects this when a SQL warehouse resource is attached to
# the app; the literal default is only a local-dev fallback.
DATABRICKS_WAREHOUSE_ID = os.environ.get("DATABRICKS_WAREHOUSE_ID", "50153ad923fecd73")
DATABRICKS_HOST = os.environ.get("DATABRICKS_HOST", "")

GOLD_TABLES = {
    "daily_store_sales": f"{GOLD_CATALOG}.{GOLD_SCHEMA}.gold_daily_store_sales",
    "category_sales": f"{GOLD_CATALOG}.{GOLD_SCHEMA}.gold_category_sales",
    "store_ranking": f"{GOLD_CATALOG}.{GOLD_SCHEMA}.gold_store_ranking",
    "unregistered_master_report": f"{GOLD_CATALOG}.{GOLD_SCHEMA}.gold_unregistered_master_report",
}

SILVER_TABLES = {
    "product_master": f"{GOLD_CATALOG}.{SILVER_SCHEMA}.silver_product_master",
    "store_master": f"{GOLD_CATALOG}.{SILVER_SCHEMA}.silver_store_master",
    # Phase 3 governance tables. DDL + seed data: retail_sales_demo/sql/.
    # NOT VERIFIED to exist in the live workspace — see docs/phase3_governance_and_ops.md.
    "user_store_mapping": f"{GOLD_CATALOG}.{SILVER_SCHEMA}.silver_user_store_mapping",
    "user_role_mapping": f"{GOLD_CATALOG}.{SILVER_SCHEMA}.silver_user_role_mapping",
    "app_audit_log": f"{GOLD_CATALOG}.{SILVER_SCHEMA}.silver_app_audit_log",
}

# Phase 3 batch job outputs, written by jobs/alert_batch.py and
# jobs/requeue_batch.py (see retail_sales_demo/jobs/). Not created by the
# API — the API only reads them.
GOLD_TABLES["store_sales_alerts"] = f"{GOLD_CATALOG}.{GOLD_SCHEMA}.gold_store_sales_alerts"
GOLD_TABLES["requeue_batch_runs"] = f"{GOLD_CATALOG}.{GOLD_SCHEMA}.gold_requeue_batch_runs"

# Demo-only stand-in for real user identity when there's no
# X-Forwarded-Email header (e.g. local dev without the Databricks Apps SSO
# proxy in front). See access_control.py.
DEMO_USER_EMAIL = os.environ.get("DEMO_USER_EMAIL", "hq-demo@example.com")

# Job ID for the quarantine re-match batch (jobs/requeue_batch.py), created
# by deploying resources/requeue_batch_job.json to the workspace. Unset
# until that deployment happens — see docs/phase3_governance_and_ops.md.
REQUEUE_JOB_ID = os.environ.get("REQUEUE_JOB_ID", "")
