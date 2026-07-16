"""GET /api/customers/{customer_id}/recommendation の疎通と応答内容を検証する。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app
from backend.services.knowledge_base import load_knowledge_docs

client = TestClient(app)


def test_recommendation_returns_200_with_expected_fields() -> None:
    response = client.get("/api/customers/C059/recommendation")
    assert response.status_code == 200
    body = response.json()

    assert body["customer_id"] == "C059"
    assert body["generation_mode"] in ("llm", "pre_generated", "rule_based")
    assert body["generation_mode_label"] in ("LLM生成", "事前生成済みLLM回答", "デモ用ルールベース生成")
    assert 1 <= len(body["actions"]) <= 3
    for action in body["actions"]:
        assert action["title"]
        assert action["reason"]
    assert isinstance(body["cautions"], list)


def test_recommendation_404_for_unknown_customer() -> None:
    response = client.get("/api/customers/NOPE/recommendation")
    assert response.status_code == 404
    assert "NOPE" in response.json()["detail"]


def test_recommendation_references_are_known_knowledge_docs() -> None:
    known_doc_ids = {doc["doc_id"] for doc in load_knowledge_docs()}

    for customer_id in ("C059", "C017", "C015", "C045", "C010", "C031", "C002"):
        response = client.get(f"/api/customers/{customer_id}/recommendation")
        assert response.status_code == 200
        body = response.json()
        for reference in body["references"]:
            assert reference["doc_id"] in known_doc_ids


def test_recommendation_never_forces_action_for_high_risk() -> None:
    """高リスク顧客でも「施策を行わず経過観察」が候補から排除されないことを確認する。"""
    list_response = client.get("/api/customers")
    high_risk_ids = [
        c["customer_id"] for c in list_response.json()["customers"] if c["risk_band"] == "high"
    ]
    assert high_risk_ids

    watch_option_present_count = 0
    for customer_id in high_risk_ids:
        response = client.get(f"/api/customers/{customer_id}/recommendation")
        titles = [action["title"] for action in response.json()["actions"]]
        if "施策を行わず経過観察" in titles:
            watch_option_present_count += 1

    # 高リスク顧客の推奨に「経過観察」が一度も現れない設計は禁止されているため、
    # 全高リスク顧客の推奨結果を見て少なくとも1件は含まれることを確認する。
    assert watch_option_present_count > 0
