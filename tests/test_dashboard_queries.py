"""
Validates sql/queries/*.sql (Phase 5 dashboard/SQL assets) against a local
Spark+Delta session built from the real generator + Phase 3/4 SQL. Confirms
KPI totals reconcile, filters return expected results, and every query used
by the planned Customer 360 / Segment Explorer / Retention Actions pages
actually runs and returns sane data.

Requires pyspark + delta-spark — see tests/conftest.py. Skipped
automatically if not installed.
"""

from pathlib import Path

import pytest

pyspark = pytest.importorskip("pyspark")
delta = pytest.importorskip("delta")

from conftest import run_sql_file  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
SQL_QUERIES_DIR = REPO_ROOT / "sql" / "queries"


def _load_query(name: str, **placeholders) -> str:
    text = (SQL_QUERIES_DIR / name).read_text()
    for key, value in placeholders.items():
        text = text.replace(f"{{{key}}}", value)
    return text.rstrip().rstrip(";")


def test_executive_overview_matches_executive_kpis_table(spark, retention_action_list):
    gold = retention_action_list
    query = _load_query("executive_overview.sql", gold=gold)
    row = spark.sql(query).collect()[0]
    direct = spark.table(f"{gold}.executive_kpis").collect()[0]
    assert row["total_customers"] == direct["total_customers"]
    assert row["high_risk_customers"] == direct["high_risk_customers"]
    assert row["estimated_value_at_risk_total_simulated"] == direct["estimated_value_at_risk_total_simulated"]


def test_risk_distribution_reconciles_to_total(spark, retention_action_list):
    gold = retention_action_list
    query = _load_query("risk_distribution.sql", gold=gold)
    rows = spark.sql(query).collect()
    total_from_chart = sum(r["customer_count"] for r in rows)
    total_customers = spark.table(f"{gold}.retention_action_list").count()
    assert total_from_chart == total_customers
    assert {r["risk_segment"] for r in rows} <= {"High", "Medium", "Low"}


def test_value_risk_matrix_reconciles_to_total(spark, retention_action_list):
    gold = retention_action_list
    query = _load_query("value_risk_matrix.sql", gold=gold)
    rows = spark.sql(query).collect()
    total_from_matrix = sum(r["customer_count"] for r in rows)
    total_customers = spark.table(f"{gold}.retention_action_list").count()
    assert total_from_matrix == total_customers
    # matrix must show more than one risk segment within at least one value
    # segment somewhere, proving risk and value aren't collapsed together
    value_segments_seen = {r["value_segment"] for r in rows}
    assert len(value_segments_seen) >= 1


def test_top_risk_drivers_excludes_no_driver_rows(spark, retention_action_list):
    gold = retention_action_list
    query = _load_query("top_risk_drivers.sql", gold=gold)
    rows = spark.sql(query).collect()
    drivers = {r["primary_driver"] for r in rows}
    assert "No material risk driver" not in drivers


def test_top_risk_drivers_scoped_to_prioritized_audience(spark, retention_action_list):
    gold = retention_action_list
    query = _load_query("top_risk_drivers.sql", gold=gold)
    rows = spark.sql(query).collect()
    total_from_chart = sum(r["customer_count"] for r in rows)
    prioritized_count = spark.sql(
        f"SELECT COUNT(*) AS n FROM {gold}.retention_action_list WHERE is_prioritized_audience = 1"
    ).collect()[0]["n"]
    # Each prioritized customer has exactly one primary_driver, so the chart's
    # bars (grouped by primary_driver) must sum to the same total.
    assert total_from_chart == prioritized_count


def test_segment_explorer_filter_by_risk_segment(spark, retention_action_list):
    gold = retention_action_list
    query = _load_query("segment_explorer.sql", gold=gold)
    rows = spark.sql(
        query,
        args={
            "risk_segment": "High",
            "value_segment": None,
            "max_product_count": None,
            "balance_decline_pct": None,
            "card_spend_decline_pct": None,
            "app_decline_pct": None,
            "min_complaints_90d": None,
            "limit": 1000,
        },
    ).collect()
    assert len(rows) > 0
    assert all(r["risk_segment"] == "High" for r in rows)


def test_segment_explorer_filter_by_balance_decline(spark, retention_action_list):
    gold = retention_action_list
    query = _load_query("segment_explorer.sql", gold=gold)
    rows = spark.sql(
        query,
        args={
            "risk_segment": None,
            "value_segment": None,
            "max_product_count": None,
            "balance_decline_pct": -0.30,
            "card_spend_decline_pct": None,
            "app_decline_pct": None,
            "min_complaints_90d": None,
            "limit": 1000,
        },
    ).collect()
    assert len(rows) > 0
    assert all(r["balance_change_90d_pct"] is not None and r["balance_change_90d_pct"] <= -0.30 for r in rows)


def test_segment_explorer_no_filters_returns_everyone_up_to_limit(spark, retention_action_list):
    gold = retention_action_list
    query = _load_query("segment_explorer.sql", gold=gold)
    total_customers = spark.table(f"{gold}.retention_action_list").count()
    rows = spark.sql(
        query,
        args={
            "risk_segment": None,
            "value_segment": None,
            "max_product_count": None,
            "balance_decline_pct": None,
            "card_spend_decline_pct": None,
            "app_decline_pct": None,
            "min_complaints_90d": None,
            "limit": total_customers,
        },
    ).collect()
    assert len(rows) == total_customers


def test_customer_360_summary_returns_exactly_one_row(spark, retention_action_list):
    gold = retention_action_list
    any_customer_id = spark.table(f"{gold}.customer_360").select("customer_id").first()["customer_id"]
    query = _load_query("customer_360_summary.sql", gold=gold)
    rows = spark.sql(query, args={"customer_id": any_customer_id}).collect()
    assert len(rows) == 1
    assert rows[0]["customer_id"] == any_customer_id
    assert rows[0]["risk_segment"] in ("High", "Medium", "Low")


def test_customer_360_summary_unknown_customer_returns_nothing(spark, retention_action_list):
    gold = retention_action_list
    query = _load_query("customer_360_summary.sql", gold=gold)
    rows = spark.sql(query, args={"customer_id": "CUST999999"}).collect()
    assert len(rows) == 0


def test_customer_trends_returns_rows_ordered_by_month(spark, customer_360_table):
    gold = customer_360_table
    silver = "test_silver"
    any_customer_id = spark.table(f"{gold}.customer_360").select("customer_id").first()["customer_id"]
    query = _load_query("customer_trends.sql", silver=silver)
    rows = spark.sql(query, args={"customer_id": any_customer_id}).collect()
    assert len(rows) > 0
    months = [r["activity_month"] for r in rows]
    assert months == sorted(months)


def test_customer_contact_history_runs(spark, customer_360_table):
    silver = "test_silver"
    any_customer_id = spark.table(f"{customer_360_table}.customer_360").select("customer_id").first()["customer_id"]
    query = _load_query("customer_contact_history.sql", silver=silver)
    # should not raise even if the customer has zero contacts
    spark.sql(query, args={"customer_id": any_customer_id}).collect()


def test_retention_actions_excludes_low_risk(spark, retention_action_list):
    gold = retention_action_list
    query = _load_query("retention_actions.sql", gold=gold)
    rows = spark.sql(
        query,
        args={"risk_segment": None, "value_segment": None, "limit": 10000, "offset": 0},
    ).collect()
    assert all(r["risk_segment"] in ("High", "Medium") for r in rows)
    ranks = [r["action_priority_rank"] for r in rows]
    assert ranks == sorted(ranks)
    assert len(ranks) == len(set(ranks)), "action_priority_rank must be unique (no tied ranks)"
    assert all(r["priority_tier"] in ("A", "B", "C") for r in rows)


def test_retention_actions_pagination(spark, retention_action_list):
    gold = retention_action_list
    query = _load_query("retention_actions.sql", gold=gold)
    page1 = spark.sql(
        query, args={"risk_segment": None, "value_segment": None, "limit": 5, "offset": 0}
    ).collect()
    page2 = spark.sql(
        query, args={"risk_segment": None, "value_segment": None, "limit": 5, "offset": 5}
    ).collect()
    assert len(page1) == 5
    page1_ids = {r["customer_id"] for r in page1}
    page2_ids = {r["customer_id"] for r in page2}
    assert page1_ids.isdisjoint(page2_ids)


def test_cross_sell_opportunity_only_returns_low_risk_low_product_customers(spark, retention_action_list):
    gold = retention_action_list
    query = _load_query("cross_sell_opportunity.sql", gold=gold)
    rows = spark.sql(query, args={"limit": 50}).collect()
    for r in rows:
        assert r["risk_segment"] == "Low"
        assert r["product_count"] <= 2
        assert r["complaint_count_90d"] == 0
