"""Pure SQL builders for the serving layer endpoints.

Each `build_*` function returns `(sql_text, params)` for use with
`db.run_query`. Parameters use the databricks-sql-connector NATIVE paramstyle
(`:name` placeholders bound server-side) so filter values are never
string-interpolated into the query text.

Keeping these as pure functions (no DB calls) lets them be unit tested
without a live Databricks connection — see backend/tests/test_queries.py.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Optional

from . import config
from .schema_assumptions import (
    CategorySales,
    DailyStoreSales,
    StoreRanking,
    UnregisteredMasterReport,
)


def _in_filter(column: str, values: Optional[list[str]], prefix: str) -> tuple[str, dict[str, Any]]:
    if not values:
        return "", {}
    placeholders = []
    params: dict[str, Any] = {}
    for i, value in enumerate(values):
        key = f"{prefix}_{i}"
        placeholders.append(f":{key}")
        params[key] = value
    return f" AND {column} IN ({', '.join(placeholders)})", params


def _date_range_filter(
    column: str, date_from: Optional[date], date_to: Optional[date]
) -> tuple[str, dict[str, Any]]:
    clauses: list[str] = []
    params: dict[str, Any] = {}
    if date_from is not None:
        clauses.append(f"{column} >= :date_from")
        params["date_from"] = date_from
    if date_to is not None:
        clauses.append(f"{column} <= :date_to")
        params["date_to"] = date_to
    return "".join(f" AND {c}" for c in clauses), params


def build_kpi_summary_query(
    store_ids: Optional[list[str]], date_from: Optional[date], date_to: Optional[date]
) -> tuple[str, dict[str, Any]]:
    table = config.GOLD_TABLES["daily_store_sales"]
    col = DailyStoreSales
    store_clause, store_params = _in_filter(f"`{col.store_id}`", store_ids, "store_id")
    date_clause, date_params = _date_range_filter(f"`{col.date}`", date_from, date_to)
    sql = f"""
        SELECT
            SUM(`{col.net_sales}`) AS net_sales,
            SUM(`{col.transaction_count}`) AS transaction_count,
            SUM(`{col.units_sold}`) AS units_sold
        FROM {table}
        WHERE 1 = 1{store_clause}{date_clause}
    """
    return sql, {**store_params, **date_params}


def build_daily_store_sales_query(
    store_ids: Optional[list[str]], date_from: Optional[date], date_to: Optional[date]
) -> tuple[str, dict[str, Any]]:
    table = config.GOLD_TABLES["daily_store_sales"]
    col = DailyStoreSales
    store_clause, store_params = _in_filter(f"`{col.store_id}`", store_ids, "store_id")
    date_clause, date_params = _date_range_filter(f"`{col.date}`", date_from, date_to)
    sql = f"""
        SELECT
            `{col.date}` AS sales_date,
            `{col.store_id}` AS store_id,
            `{col.store_name}` AS store_name,
            `{col.net_sales}` AS net_sales,
            `{col.transaction_count}` AS transaction_count,
            `{col.units_sold}` AS units_sold
        FROM {table}
        WHERE 1 = 1{store_clause}{date_clause}
        ORDER BY `{col.date}` ASC, `{col.store_id}` ASC
    """
    return sql, {**store_params, **date_params}


def build_category_sales_query(
    store_ids: Optional[list[str]], date_from: Optional[date], date_to: Optional[date]
) -> tuple[str, dict[str, Any]]:
    table = config.GOLD_TABLES["category_sales"]
    col = CategorySales
    store_clause, store_params = _in_filter(f"`{col.store_id}`", store_ids, "store_id")
    date_clause, date_params = _date_range_filter(f"`{col.date}`", date_from, date_to)
    sql = f"""
        SELECT
            `{col.category_id}` AS category_id,
            `{col.category_name}` AS category_name,
            SUM(`{col.net_sales}`) AS net_sales,
            SUM(`{col.units_sold}`) AS units_sold
        FROM {table}
        WHERE 1 = 1{store_clause}{date_clause}
        GROUP BY `{col.category_id}`, `{col.category_name}`
        ORDER BY net_sales DESC
    """
    return sql, {**store_params, **date_params}


def build_store_ranking_query(
    store_ids: Optional[list[str]], date_from: Optional[date], date_to: Optional[date]
) -> tuple[str, dict[str, Any]]:
    table = config.GOLD_TABLES["store_ranking"]
    col = StoreRanking
    store_clause, store_params = _in_filter(f"`{col.store_id}`", store_ids, "store_id")
    date_clause, date_params = _date_range_filter(f"`{col.date}`", date_from, date_to)
    sql = f"""
        SELECT
            `{col.date}` AS ranking_date,
            `{col.store_id}` AS store_id,
            `{col.store_name}` AS store_name,
            `{col.net_sales}` AS net_sales,
            `{col.rank}` AS rank
        FROM {table}
        WHERE 1 = 1{store_clause}{date_clause}
        ORDER BY `{col.rank}` ASC
    """
    return sql, {**store_params, **date_params}


def build_quarantine_report_query(
    store_ids: Optional[list[str]],
    issue_types: Optional[list[str]],
    date_from: Optional[date],
    date_to: Optional[date],
) -> tuple[str, dict[str, Any]]:
    table = config.GOLD_TABLES["unregistered_master_report"]
    col = UnregisteredMasterReport
    store_clause, store_params = _in_filter(f"`{col.store_id}`", store_ids, "store_id")
    issue_clause, issue_params = _in_filter(f"`{col.issue_type}`", issue_types, "issue_type")
    date_clause, date_params = _date_range_filter(f"`{col.date}`", date_from, date_to)
    sql = f"""
        SELECT
            `{col.date}` AS transaction_date,
            `{col.transaction_id}` AS transaction_id,
            `{col.store_id}` AS store_id,
            `{col.product_id}` AS product_id,
            `{col.issue_type}` AS issue_type,
            `{col.net_sales}` AS net_sales,
            `{col.quantity}` AS quantity
        FROM {table}
        WHERE 1 = 1{store_clause}{issue_clause}{date_clause}
        ORDER BY `{col.date}` DESC
    """
    return sql, {**store_params, **issue_params, **date_params}
