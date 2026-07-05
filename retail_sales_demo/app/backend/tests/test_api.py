"""API-level tests with the Databricks SQL call mocked out.

This verifies request/response wiring (params parsing, response schema,
gross_sales estimation flag) end-to-end through FastAPI. It does NOT verify
that the queries return correct data against the real Warehouse/tables —
this session has no network access to the Databricks workspace (see
docs/phase0_env_setup_check.md), so that verification must happen in an
environment that can reach it.
"""
from fastapi.testclient import TestClient

from backend import main


def test_kpi_summary_marks_gross_sales_as_estimated(monkeypatch):
    monkeypatch.setattr(
        main,
        "run_query",
        lambda sql, params: [
            {"net_sales": 1000.0, "transaction_count": 10, "units_sold": 25}
        ],
    )
    client = TestClient(main.app)
    resp = client.get("/api/kpi-summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["net_sales"] == 1000.0
    assert body["gross_sales"] == 1000.0
    assert body["gross_sales_is_estimated"] is True
    assert body["average_basket_size"] == 100.0


def test_kpi_summary_handles_zero_transactions(monkeypatch):
    monkeypatch.setattr(main, "run_query", lambda sql, params: [])
    client = TestClient(main.app)
    resp = client.get("/api/kpi-summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["net_sales"] == 0
    assert body["average_basket_size"] is None


def test_daily_store_sales_passes_store_id_filter(monkeypatch):
    captured = {}

    def fake_run_query(sql, params):
        captured["sql"] = sql
        captured["params"] = params
        return []

    monkeypatch.setattr(main, "run_query", fake_run_query)
    client = TestClient(main.app)
    resp = client.get("/api/daily-store-sales", params={"store_id": "S001,S002"})
    assert resp.status_code == 200
    assert captured["params"] == {"store_id_0": "S001", "store_id_1": "S002"}


def test_category_sales_computes_share_of_net_sales(monkeypatch):
    monkeypatch.setattr(
        main,
        "run_query",
        lambda sql, params: [
            {"category_id": "C1", "category_name": "Food", "net_sales": 300.0, "units_sold": 10},
            {"category_id": "C2", "category_name": "Goods", "net_sales": 700.0, "units_sold": 5},
        ],
    )
    client = TestClient(main.app)
    resp = client.get("/api/category-sales")
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["share_of_net_sales"] == 0.3
    assert body[1]["share_of_net_sales"] == 0.7


def test_quarantine_report_passes_issue_type_filter(monkeypatch):
    captured = {}

    def fake_run_query(sql, params):
        captured["params"] = params
        return []

    monkeypatch.setattr(main, "run_query", fake_run_query)
    client = TestClient(main.app)
    resp = client.get("/api/quarantine-report", params={"issue_type": "UNKNOWN_PRODUCT"})
    assert resp.status_code == 200
    assert captured["params"] == {"issue_type_0": "UNKNOWN_PRODUCT"}
