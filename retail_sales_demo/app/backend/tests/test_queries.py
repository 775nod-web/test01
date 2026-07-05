"""Unit tests for the pure SQL query builders (no live Databricks connection).

These verify the WHERE-clause / parameter wiring that main.py depends on.
They cannot verify that the assumed column names in schema_assumptions.py
match the real Unity Catalog tables — that requires a live connection
(see docs/phase1_serving_layer_api.md).
"""
from datetime import date

from backend import queries


def test_kpi_summary_no_filters():
    sql, params = queries.build_kpi_summary_query(None, None, None)
    assert "SUM(`net_sales`)" in sql
    assert "WHERE 1 = 1" in sql
    assert params == {}


def test_kpi_summary_with_store_and_date_filters():
    sql, params = queries.build_kpi_summary_query(
        ["S001", "S002"], date(2026, 1, 1), date(2026, 1, 31)
    )
    assert "`store_id` IN (:store_id_0, :store_id_1)" in sql
    assert "`sales_date` >= :date_from" in sql
    assert "`sales_date` <= :date_to" in sql
    assert params == {
        "store_id_0": "S001",
        "store_id_1": "S002",
        "date_from": date(2026, 1, 1),
        "date_to": date(2026, 1, 31),
    }


def test_daily_store_sales_orders_by_date_and_store():
    sql, _ = queries.build_daily_store_sales_query(None, None, None)
    assert "ORDER BY `sales_date` ASC, `store_id` ASC" in sql


def test_category_sales_groups_by_category():
    sql, params = queries.build_category_sales_query(["S001"], None, None)
    assert "GROUP BY `category_id`, `category_name`" in sql
    assert params == {"store_id_0": "S001"}


def test_store_ranking_orders_by_rank():
    sql, _ = queries.build_store_ranking_query(None, None, None)
    assert "ORDER BY `rank` ASC" in sql


def test_quarantine_report_filters_by_issue_type_and_store():
    sql, params = queries.build_quarantine_report_query(
        ["S001"], ["UNKNOWN_PRODUCT", "UNKNOWN_STORE"], None, None
    )
    assert "`store_id` IN (:store_id_0)" in sql
    assert "`issue_type` IN (:issue_type_0, :issue_type_1)" in sql
    assert params == {
        "store_id_0": "S001",
        "issue_type_0": "UNKNOWN_PRODUCT",
        "issue_type_1": "UNKNOWN_STORE",
    }


def test_no_filters_produce_no_params_across_all_builders():
    for sql, params in [
        queries.build_kpi_summary_query(None, None, None),
        queries.build_daily_store_sales_query(None, None, None),
        queries.build_category_sales_query(None, None, None),
        queries.build_store_ranking_query(None, None, None),
        queries.build_quarantine_report_query(None, None, None, None),
    ]:
        assert params == {}
        assert " AND " not in sql or "WHERE 1 = 1" in sql
