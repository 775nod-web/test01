"""判断保存（/api/customers/{id}/decision）とフィードバック概要（/api/feedback-summary）を検証する。

判断はファイルへ書き込まれる副作用を持つため、各テストで一時ファイルへ差し替える。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services import decision_store

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolate_decision_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """各テストで判断保存先を一時ファイルへ差し替え、実行環境のruntime/を汚さないようにする。"""
    monkeypatch.setattr(decision_store, "DEFAULT_DECISIONS_PATH", tmp_path / "decisions.json")


def test_post_decision_returns_saved_record_with_decided_at() -> None:
    response = client.post(
        "/api/customers/C001/decision",
        json={
            "decision": "approved",
            "selected_action": "EC再利用の案内",
            "comment": "承認します",
            "generation_mode": "rule_based",
            "model_version": "rule-based-v1",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["customer_id"] == "C001"
    assert body["decision"] == "approved"
    assert body["decision_id"]
    assert body["decided_at"]


def test_post_decision_404_for_unknown_customer() -> None:
    response = client.post("/api/customers/NOPE/decision", json={"decision": "skipped"})
    assert response.status_code == 404


def test_post_decision_rejects_invalid_decision_value() -> None:
    response = client.post("/api/customers/C001/decision", json={"decision": "invalid-value"})
    assert response.status_code == 422


def test_feedback_summary_starts_empty() -> None:
    response = client.get("/api/feedback-summary")
    assert response.status_code == 200
    body = response.json()
    assert body["total_decisions"] == 0
    assert body["approved_count"] == 0
    assert body["modified_count"] == 0
    assert body["skipped_count"] == 0
    assert body["recent_decisions"] == []


def test_feedback_summary_reflects_saved_decisions() -> None:
    client.post(
        "/api/customers/C001/decision",
        json={"decision": "approved", "generation_mode": "rule_based"},
    )
    client.post(
        "/api/customers/C002/decision",
        json={"decision": "skipped", "generation_mode": "pre_generated"},
    )
    client.post(
        "/api/customers/C003/decision",
        json={
            "decision": "modified",
            "modified_text": "修正した内容",
            "generation_mode": "rule_based",
        },
    )

    response = client.get("/api/feedback-summary")
    assert response.status_code == 200
    body = response.json()

    assert body["total_decisions"] == 3
    assert body["approved_count"] == 1
    assert body["skipped_count"] == 1
    assert body["modified_count"] == 1
    assert body["by_generation_mode"]["rule_based"] == 2
    assert body["by_generation_mode"]["pre_generated"] == 1
    assert len(body["recent_decisions"]) == 3
    assert body["recent_decisions"][0]["display_name"]  # 顧客360と結合して表示名が入っていること


def test_feedback_summary_notes_auto_retraining_is_not_implemented() -> None:
    response = client.get("/api/feedback-summary")
    assert "本番化" in response.json()["note"]
