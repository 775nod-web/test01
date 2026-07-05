"""Assumed Gold-layer column names used by queries.py.

*** ASSUMPTION — NOT VERIFIED AGAINST THE LIVE UNITY CATALOG SCHEMA ***
This coding session has no network access to the Databricks workspace (see
docs/phase0_env_setup_check.md), so these column names could not be confirmed
with `DESCRIBE TABLE workspace.gold.<table>`. Before deploying, run
`DESCRIBE TABLE` against each of the four gold tables and update the
constants below if they differ — queries.py only ever references columns
through these classes, so a schema mismatch is a one-file fix.
"""


class DailyStoreSales:
    date = "sales_date"
    store_id = "store_id"
    store_name = "store_name"
    net_sales = "net_sales"
    transaction_count = "transaction_count"
    units_sold = "units_sold"


class CategorySales:
    date = "sales_date"
    store_id = "store_id"
    store_name = "store_name"
    category_id = "category_id"
    category_name = "category_name"
    net_sales = "net_sales"
    units_sold = "units_sold"


class StoreRanking:
    date = "ranking_date"
    store_id = "store_id"
    store_name = "store_name"
    net_sales = "net_sales"
    rank = "rank"


class UnregisteredMasterReport:
    date = "transaction_date"
    transaction_id = "transaction_id"
    store_id = "store_id"
    product_id = "product_id"
    issue_type = "issue_type"
    net_sales = "net_sales"
    quantity = "quantity"
    # Phase 3: PII column added on top of the Phase 1 assumption above — the
    # Phase 1 investigation never confirmed whether this table even has a
    # customer identifier column. Masked for callers without PII_VIEWER
    # (see access_control.py) if/once confirmed to exist.
    customer_id = "customer_id"


# --- Phase 3 governance/ops tables (DDL: retail_sales_demo/sql/) ---


class UserStoreMapping:
    user_email = "user_email"
    store_id = "store_id"  # special value "ALL" grants every store


class UserRoleMapping:
    user_email = "user_email"
    role = "role"  # e.g. "PII_VIEWER", "AUDIT_VIEWER"


class AppAuditLog:
    logged_at = "logged_at"
    user_email = "user_email"
    endpoint = "endpoint"
    store_id_filter = "store_id_filter"
    status_code = "status_code"


class StoreSalesAlert:
    alert_date = "alert_date"
    store_id = "store_id"
    store_name = "store_name"
    comparison_type = "comparison_type"  # "DoD" or "WoW"
    current_value = "current_value"
    previous_value = "previous_value"
    pct_change = "pct_change"
    threshold_pct = "threshold_pct"
    triggered_at = "triggered_at"


class RequeueBatchRun:
    run_id = "run_id"
    started_at = "started_at"
    status = "status"
    records_checked = "records_checked"
    reconciled_candidates_found = "reconciled_candidates_found"
