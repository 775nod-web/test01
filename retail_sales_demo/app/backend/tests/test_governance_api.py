"""API-level tests for the Phase 3 governance/ops endpoints and access-control
wiring, with run_query/access_control mocked (no live Databricks connection —
see docs/phase3_governance_and_ops.md)."""
from fastapi.testclient import TestClient

from backend import access_control, config, main
from backend.access_control import AccessContext


def _set_context(monkeypatch, **kwargs):
    defaults = dict(user_email="test@example.com", allowed_store_ids=None, roles=set())
    defaults.update(kwargs)
    monkeypatch.setattr(access_control, "get_access_context", lambda user_email: AccessContext(**defaults))


def test_me_reflects_resolved_identity(monkeypatch):
    _set_context(monkeypatch, user_email="store1@example.com", allowed_store_ids=["S001"], roles={"PII_VIEWER"})
    client = TestClient(main.app)
    resp = client.get("/api/me", headers={"X-Forwarded-Email": "store1@example.com"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["user_email"] == "store1@example.com"
    assert body["allowed_store_ids"] == ["S001"]
    assert body["roles"] == ["PII_VIEWER"]


def test_daily_store_sales_denies_when_requested_store_not_allowed(monkeypatch):
    _set_context(monkeypatch, allowed_store_ids=["S001"])
    captured = {"called": False}
    monkeypatch.setattr(main, "run_query", lambda sql, params: captured.update(called=True) or [])
    client = TestClient(main.app)
    resp = client.get("/api/daily-store-sales", params={"store_id": "S999"})
    assert resp.status_code == 200
    assert resp.json() == []
    assert captured["called"] is False  # denied before ever hitting the Warehouse


def test_daily_store_sales_intersects_requested_with_allowed(monkeypatch):
    _set_context(monkeypatch, allowed_store_ids=["S001", "S002"])
    captured = {}

    def fake_run_query(sql, params):
        captured["params"] = params
        return []

    monkeypatch.setattr(main, "run_query", fake_run_query)
    client = TestClient(main.app)
    resp = client.get("/api/daily-store-sales", params={"store_id": "S001,S003"})
    assert resp.status_code == 200
    assert captured["params"] == {"store_id_0": "S001"}  # S003 dropped, not in allowed set


def test_kpi_summary_denies_without_querying(monkeypatch):
    _set_context(monkeypatch, allowed_store_ids=["S001"])
    captured = {"called": False}
    monkeypatch.setattr(main, "run_query", lambda sql, params: captured.update(called=True) or [])
    client = TestClient(main.app)
    resp = client.get("/api/kpi-summary", params={"store_id": "S999"})
    assert resp.status_code == 200
    assert resp.json()["net_sales"] == 0
    assert captured["called"] is False


def test_quarantine_report_masks_customer_id_without_pii_role(monkeypatch):
    _set_context(monkeypatch, allowed_store_ids=["S001"], roles=set())
    monkeypatch.setattr(
        main,
        "run_query",
        lambda sql, params: [
            {
                "transaction_date": "2026-06-01",
                "transaction_id": "T0001",
                "store_id": "S001",
                "product_id": None,
                "issue_type": "UNKNOWN_PRODUCT",
                "net_sales": 100.0,
                "quantity": 1,
                "customer_id": "CUST12345",
            }
        ],
    )
    client = TestClient(main.app)
    resp = client.get("/api/quarantine-report")
    body = resp.json()[0]
    assert body["customer_id_is_masked"] is True
    assert body["customer_id"] == "CUST*****"


def test_quarantine_report_shows_customer_id_with_pii_role(monkeypatch):
    _set_context(monkeypatch, allowed_store_ids=None, roles={"PII_VIEWER"})
    monkeypatch.setattr(
        main,
        "run_query",
        lambda sql, params: [
            {
                "transaction_date": "2026-06-01",
                "transaction_id": "T0001",
                "store_id": "S001",
                "product_id": None,
                "issue_type": "UNKNOWN_PRODUCT",
                "net_sales": 100.0,
                "quantity": 1,
                "customer_id": "CUST12345",
            }
        ],
    )
    client = TestClient(main.app)
    resp = client.get("/api/quarantine-report")
    body = resp.json()[0]
    assert body["customer_id_is_masked"] is False
    assert body["customer_id"] == "CUST12345"


def test_alerts_endpoint_reads_latest_alerts(monkeypatch):
    monkeypatch.setattr(
        main,
        "run_query",
        lambda sql, params: [
            {
                "alert_date": "2026-07-04",
                "store_id": "S003",
                "store_name": "店舗3",
                "comparison_type": "DoD",
                "current_value": 40000.0,
                "previous_value": 60000.0,
                "pct_change": -33.3,
                "threshold_pct": -20.0,
            }
        ],
    )
    client = TestClient(main.app)
    resp = client.get("/api/alerts")
    assert resp.status_code == 200
    assert resp.json()[0]["store_id"] == "S003"


def test_audit_log_requires_audit_viewer_role(monkeypatch):
    _set_context(monkeypatch, allowed_store_ids=["S001"], roles=set())
    client = TestClient(main.app)
    resp = client.get("/api/audit-log")
    assert resp.status_code == 403


def test_audit_log_available_to_admin(monkeypatch):
    _set_context(monkeypatch, allowed_store_ids=None, roles=set())
    monkeypatch.setattr(main, "run_query", lambda sql, params: [])
    client = TestClient(main.app)
    resp = client.get("/api/audit-log")
    assert resp.status_code == 200


def test_requeue_status_handles_no_runs_yet(monkeypatch):
    monkeypatch.setattr(main, "run_query", lambda sql, params: [])
    client = TestClient(main.app)
    resp = client.get("/api/requeue-status")
    assert resp.status_code == 200
    assert resp.json()["run_id"] is None


def test_requeue_trigger_returns_501_when_job_not_deployed(monkeypatch):
    monkeypatch.setattr(config, "REQUEUE_JOB_ID", "")
    client = TestClient(main.app)
    resp = client.post("/api/requeue-trigger")
    assert resp.status_code == 501
