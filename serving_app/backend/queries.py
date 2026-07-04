"""gold.* の4表に対する読み取り専用クエリ。

Serving layerはGold layerの集計結果を配信するだけの役割のため、
ここでは単純なSELECT文のみを発行し、書き込みは一切行わない。
"""

import datetime
import decimal
from typing import Any

from .db import get_connection, qualified_table


def _to_jsonable(value: Any) -> Any:
    """databricks-sql-connectorが返す date / Decimal 等をJSONで表現できる型に変換する"""
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return float(value)
    return value


def _fetch_all(query: str) -> list[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()
            return [
                {col: _to_jsonable(val) for col, val in zip(columns, row)}
                for row in rows
            ]


def fetch_daily_store_sales() -> list[dict[str, Any]]:
    table = qualified_table("gold_daily_store_sales")
    query = f"""
        SELECT sales_date, store_id, store_name, region,
               transaction_count, total_quantity, total_sales_amount
        FROM {table}
        ORDER BY sales_date, store_id
    """
    return _fetch_all(query)


def fetch_category_sales() -> list[dict[str, Any]]:
    table = qualified_table("gold_category_sales")
    query = f"""
        SELECT category, product_count, transaction_count,
               total_quantity, total_sales_amount
        FROM {table}
        ORDER BY total_sales_amount DESC
    """
    return _fetch_all(query)


def fetch_store_ranking() -> list[dict[str, Any]]:
    table = qualified_table("gold_store_ranking")
    query = f"""
        SELECT sales_rank, store_id, store_name, region, store_type,
               total_sales_amount, total_quantity, transaction_count
        FROM {table}
        ORDER BY sales_rank
    """
    return _fetch_all(query)


def fetch_unregistered_master_report() -> list[dict[str, Any]]:
    table = qualified_table("gold_unregistered_master_report")
    query = f"""
        SELECT transaction_id, issue_type, store_id, is_store_registered,
               product_id, is_product_registered, customer_id,
               transaction_datetime, quantity, unit_price,
               discount_amount, sales_amount
        FROM {table}
        ORDER BY transaction_id
    """
    return _fetch_all(query)
