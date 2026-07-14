"""
Backend API tests using FastAPI's TestClient against the local DuckDB
fallback engine (backend/local_fixtures/*.parquet, committed to the repo).
Does not require a Databricks connection. Requires `duckdb` (see
requirements-dev.txt) — skipped gracefully if not installed.
"""

import pytest

pytest.importorskip("duckdb")

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402

client = TestClient(app)


def test_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["data_mode"] == "local"


def test_kpis():
    res = client.get("/api/kpis")
    assert res.status_code == 200
    body = res.json()
    assert body["total_customers"] > 0
    assert (
        body["high_risk_customers"] + body["medium_risk_customers"] + body["low_risk_customers"]
        == body["total_customers"]
    )


def test_risk_distribution():
    res = client.get("/api/risk-distribution")
    assert res.status_code == 200
    body = res.json()
    assert {row["risk_segment"] for row in body} <= {"High", "Medium", "Low"}


def test_value_risk_matrix():
    res = client.get("/api/value-risk-matrix")
    assert res.status_code == 200
    assert len(res.json()) > 0


def test_top_risk_drivers():
    res = client.get("/api/top-risk-drivers")
    assert res.status_code == 200
    for row in res.json():
        assert row["primary_driver"] != "No material risk driver"


def test_segments_filter_options():
    res = client.get("/api/segments")
    assert res.status_code == 200
    body = res.json()
    assert body["risk_segments"] == ["High", "Medium", "Low"]


def test_customers_list_default():
    res = client.get("/api/customers")
    assert res.status_code == 200
    body = res.json()
    assert body["count"] == len(body["items"])
    assert body["count"] <= 200


def test_customers_list_invalid_risk_segment_rejected():
    res = client.get("/api/customers", params={"risk_segment": "Extreme"})
    assert res.status_code == 422  # FastAPI query validation


def test_customers_list_filter_by_risk_segment():
    res = client.get("/api/customers", params={"risk_segment": "High", "limit": 500})
    assert res.status_code == 200
    body = res.json()
    assert all(item["risk_segment"] == "High" for item in body["items"])


def test_customer_detail_found():
    listing = client.get("/api/customers", params={"limit": 1}).json()
    customer_id = listing["items"][0]["customer_id"]
    res = client.get(f"/api/customers/{customer_id}")
    assert res.status_code == 200
    body = res.json()
    assert body["customer_id"] == customer_id
    assert isinstance(body["trends"], list) and len(body["trends"]) > 0
    assert isinstance(body["contact_history"], list)


def test_customer_detail_not_found():
    res = client.get("/api/customers/NOPE000000")
    assert res.status_code == 404


def test_retention_actions_excludes_low_risk():
    res = client.get("/api/retention-actions", params={"limit": 500})
    assert res.status_code == 200
    body = res.json()
    assert all(item["risk_segment"] in ("High", "Medium") for item in body["items"])


def test_retention_actions_pagination_no_overlap():
    page1 = client.get("/api/retention-actions", params={"limit": 5, "offset": 0}).json()["items"]
    page2 = client.get("/api/retention-actions", params={"limit": 5, "offset": 5}).json()["items"]
    ids1 = {r["customer_id"] for r in page1}
    ids2 = {r["customer_id"] for r in page2}
    assert ids1.isdisjoint(ids2)


def test_retention_actions_export_csv():
    res = client.get("/api/retention-actions/export")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/csv")
    lines = res.text.strip().splitlines()
    assert lines[0].startswith("customer_id,")
    assert len(lines) > 1


def test_poc_summary():
    res = client.get("/api/poc-summary")
    assert res.status_code == 200
    body = res.json()
    assert len(body["synthetic_elements"]) > 0
    assert len(body["free_edition_limitations"]) > 0
    for candidate in body["cross_sell_sample"]:
        assert candidate["risk_segment"] == "Low"


def test_unknown_route_falls_back_to_spa_index_or_404():
    # With backend/static/ built, unknown non-API paths serve the SPA index
    # (client-side routing); without a build, FastAPI's own 404 applies.
    res = client.get("/some/made/up/path")
    assert res.status_code in (200, 404)
