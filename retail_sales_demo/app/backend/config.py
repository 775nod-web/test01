import os

GOLD_CATALOG = os.environ.get("GOLD_CATALOG", "workspace")
GOLD_SCHEMA = os.environ.get("GOLD_SCHEMA", "gold")
SILVER_SCHEMA = os.environ.get("SILVER_SCHEMA", "silver")
SQL_WAREHOUSE_ID = os.environ.get("SQL_WAREHOUSE_ID", "50153ad923fecd73")

GOLD_TABLES = {
    "daily_store_sales": f"{GOLD_CATALOG}.{GOLD_SCHEMA}.gold_daily_store_sales",
    "category_sales": f"{GOLD_CATALOG}.{GOLD_SCHEMA}.gold_category_sales",
    "store_ranking": f"{GOLD_CATALOG}.{GOLD_SCHEMA}.gold_store_ranking",
    "unregistered_master_report": f"{GOLD_CATALOG}.{GOLD_SCHEMA}.gold_unregistered_master_report",
}

SILVER_TABLES = {
    "product_master": f"{GOLD_CATALOG}.{SILVER_SCHEMA}.silver_product_master",
    "store_master": f"{GOLD_CATALOG}.{SILVER_SCHEMA}.silver_store_master",
}
