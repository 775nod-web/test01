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


def test_quarantine_report_selects_customer_id_for_masking():
    sql, _ = queries.build_quarantine_report_query(None, None, None, None)
    assert "`customer_id` AS customer_id" in sql


def test_user_store_mapping_query_filters_by_user():
    sql, params = queries.build_user_store_mapping_query("store1@example.com")
    assert "`user_email` = :user_email" in sql
    assert params == {"user_email": "store1@example.com"}


def test_user_role_mapping_query_filters_by_user():
    sql, params = queries.build_user_role_mapping_query("dq@example.com")
    assert "`user_email` = :user_email" in sql
    assert params == {"user_email": "dq@example.com"}


def test_audit_log_insert_binds_all_fields():
    sql, params = queries.build_audit_log_insert("u@example.com", "/api/kpi-summary", "S001", 200)
    assert "INSERT INTO" in sql
    assert params == {
        "user_email": "u@example.com",
        "endpoint": "/api/kpi-summary",
        "store_id_filter": "S001",
        "status_code": 200,
    }


def test_audit_log_query_orders_by_logged_at_desc():
    sql, params = queries.build_audit_log_query(50)
    assert "ORDER BY `logged_at` DESC" in sql
    assert params == {"limit": 50}


def test_alerts_query_filters_by_latest_date_and_store():
    sql, params = queries.build_alerts_query(["S001"])
    assert "MAX(`alert_date`)" in sql
    assert "`store_id` IN (:store_id_0)" in sql
    assert params == {"store_id_0": "S001"}


def test_requeue_status_query_gets_latest_run():
    sql, params = queries.build_requeue_status_query()
    assert "ORDER BY `started_at` DESC" in sql
    assert "LIMIT 1" in sql
    assert params == {}
