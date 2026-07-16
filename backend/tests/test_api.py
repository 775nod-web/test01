"""/api/health と /api/metadata の疎通を検証する。"""

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_health_returns_200_ok() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_metadata_returns_mode_information() -> None:
    response = client.get("/api/metadata")
    assert response.status_code == 200
    body = response.json()
    assert body["data_mode"] in ("demo", "databricks")
    assert "updated_at" in body
    assert "app_name" in body
