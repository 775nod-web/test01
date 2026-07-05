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
