"""GET /api/customers/{customer_id}/recommendation の疎通と応答内容を検証する。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app
from backend.services.data_source import load_customer_dataset
from backend.services.knowledge_base import load_knowledge_docs

client = TestClient(app)

CAMPAIGN_TYPE_TO_ACTION_TITLE = {
    "QR決済ポイント還元": "QR決済の利用メリット案内",
    "カード利用特典案内": "カード利用特典の案内",
    "EC再訪促進メール": "EC再利用の案内",
    "複数サービス横断ポイント施策": "複数サービスをまたぐ軽量なポイント施策",
}


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


def test_recommendation_acknowledges_past_no_response_for_same_channel() -> None:
    """過去に同じ種類の施策へ「反応なし」だった場合、推奨がそれを踏まえていることを確認する
    （推奨アクションが過去の反応と矛盾しないための回帰テスト）。"""
    dataset = load_customer_dataset()
    checked_any = False

    for customer_id, customer in dataset.customers_by_id.items():
        for campaign in customer.get("campaigns", []):
            if campaign["response"] != "反応なし":
                continue
            action_title = CAMPAIGN_TYPE_TO_ACTION_TITLE.get(campaign["campaign_type"])
            if action_title is None:
                continue

            response = client.get(f"/api/customers/{customer_id}/recommendation")
            body = response.json()
            recommended_titles = [a["title"] for a in body["actions"]]
            if action_title not in recommended_titles:
                continue

            checked_any = True
            caution_text = " ".join(body["cautions"])
            assert campaign["campaign_type"] in caution_text, (
                f"{customer_id}: '{action_title}' recommended despite past "
                f"'反応なし' on '{campaign['campaign_type']}', but no caution mentions it"
            )

    assert checked_any, "no customer exercised the no-response contradiction path"
