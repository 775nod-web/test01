"""GET /api/customers, GET /api/customers/{customer_id} の疎通と応答内容を検証する。

これらのテストは artifacts/ 配下にコミット済みの事前計算済みデータ
（フォールバック用データ）を前提とする。scripts/generate_demo_data.py →
scripts/prepare_customer360.py → scripts/train_model.py の実行結果が
リポジトリに保存されていることを検証する意味も兼ねる。
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_customers_list_returns_envelope_and_customers() -> None:
    response = client.get("/api/customers")
    assert response.status_code == 200
    body = response.json()

    assert body["data_mode"] in ("demo", "databricks")
    assert body["model_mode"] in ("trained", "precomputed")
    assert "updated_at" in body
    assert 30 <= len(body["customers"]) <= 80


def test_customers_list_sorted_by_churn_probability_descending() -> None:
    response = client.get("/api/customers")
    probabilities = [c["churn_probability"] for c in response.json()["customers"]]
    assert probabilities == sorted(probabilities, reverse=True)


def test_customers_list_includes_all_three_risk_bands() -> None:
    response = client.get("/api/customers")
    bands = {c["risk_band"] for c in response.json()["customers"]}
    assert bands == {"high", "medium", "low"}


def test_customer_detail_returns_customer_and_prediction() -> None:
    list_response = client.get("/api/customers")
    first_customer_id = list_response.json()["customers"][0]["customer_id"]

    response = client.get(f"/api/customers/{first_customer_id}")
    assert response.status_code == 200
    body = response.json()

    assert body["customer"]["customer_id"] == first_customer_id
    assert body["prediction"]["risk_band"] in ("high", "medium", "low")
    assert 0 < body["prediction"]["churn_probability"] < 1
    assert 1 <= len(body["prediction"]["reasons"]) <= 3


def test_customer_detail_404_for_unknown_customer() -> None:
    response = client.get("/api/customers/NOPE")
    assert response.status_code == 404
    assert "NOPE" in response.json()["detail"]


def test_metadata_reflects_customer_dataset() -> None:
    response = client.get("/api/metadata")
    assert response.status_code == 200
    body = response.json()
    assert body["data_mode"] in ("demo", "databricks")
    assert body["model_mode"] in ("trained", "precomputed")
    assert 30 <= body["customer_count"] <= 80
