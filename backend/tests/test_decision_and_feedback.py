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
    assert body["persisted"] is True


def test_post_decision_rejects_overlong_comment() -> None:
    response = client.post(
        "/api/customers/C001/decision",
        json={"decision": "approved", "comment": "x" * 2001},
    )
    assert response.status_code == 422


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
    # 判断記録が無くても施策後の反応サンプルは取得でき、担当者判断はNoneになる
    assert len(body["sample_outcomes"]) > 0
    assert all(outcome["decision"] is None for outcome in body["sample_outcomes"])


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


def test_sample_outcomes_are_fixed_and_flagged_as_sample() -> None:
    """施策後の反応・利用再開サンプルは固定データであり、再取得しても変化しない。"""
    first = client.get("/api/feedback-summary").json()["sample_outcomes"]
    second = client.get("/api/feedback-summary").json()["sample_outcomes"]
    assert first == second
    assert len(first) >= 3
    assert all(outcome["is_sample"] is True for outcome in first)


def test_sample_outcomes_customer_ids_exist_in_customer360() -> None:
    outcomes = client.get("/api/feedback-summary").json()["sample_outcomes"]
    customers_response = client.get("/api/customers").json()
    known_ids = {c["customer_id"] for c in customers_response["customers"]}
    for outcome in outcomes:
        assert outcome["customer_id"] in known_ids
        assert outcome["customer_response"]
        assert outcome["usage_recovery_status"]


def test_sample_outcome_reflects_saved_decision_for_same_customer() -> None:
    """サンプル対象顧客に実際の判断を保存すると、その顧客の行に担当者判断が反映される。"""
    outcomes_before = client.get("/api/feedback-summary").json()["sample_outcomes"]
    sample_customer_id = outcomes_before[0]["customer_id"]

    client.post(
        f"/api/customers/{sample_customer_id}/decision",
        json={
            "decision": "approved",
            "selected_action": "複数サービスをまたぐ軽量なポイント施策",
            "comment": "テスト用の承認",
            "generation_mode": "rule_based",
        },
    )

    outcomes_after = client.get("/api/feedback-summary").json()["sample_outcomes"]
    matched = next(o for o in outcomes_after if o["customer_id"] == sample_customer_id)
    assert matched["decision"] == "approved"
    assert matched["comment"] == "テスト用の承認"
    assert matched["decided_at"]
    # 施策後の反応・利用再開自体はサンプルのまま変化しない
    original = next(o for o in outcomes_before if o["customer_id"] == sample_customer_id)
    assert matched["customer_response"] == original["customer_response"]
    assert matched["usage_recovery_status"] == original["usage_recovery_status"]


def test_sample_outcomes_do_not_break_existing_feedback_summary_fields() -> None:
    """既存フィールドが引き続き揃っていることを確認する（後方互換性）。"""
    body = client.get("/api/feedback-summary").json()
    for key in (
        "total_decisions",
        "approved_count",
        "modified_count",
        "skipped_count",
        "by_generation_mode",
        "recent_decisions",
        "updated_at",
        "storage_mode",
        "persisted",
    ):
        assert key in body


def test_sample_outcomes_include_recommended_next_action() -> None:
    outcomes = client.get("/api/feedback-summary").json()["sample_outcomes"]
    for outcome in outcomes:
        action = outcome["recommended_next_action"]
        assert action["type"]
        assert action["label"]
        assert action["reason"]
        assert action["next_review_timing"]


def test_skipped_decision_updates_recommended_next_action_to_review_targeting() -> None:
    outcomes_before = client.get("/api/feedback-summary").json()["sample_outcomes"]
    sample_customer_id = outcomes_before[0]["customer_id"]

    client.post(
        f"/api/customers/{sample_customer_id}/decision",
        json={"decision": "skipped", "comment": "今回は対象外"},
    )

    outcomes_after = client.get("/api/feedback-summary").json()["sample_outcomes"]
    matched = next(o for o in outcomes_after if o["customer_id"] == sample_customer_id)
    assert matched["recommended_next_action"]["type"] == "対象顧客の条件を見直す"


def test_feedback_summary_includes_improvement_summary_with_expected_keys() -> None:
    body = client.get("/api/feedback-summary").json()
    summary = body["improvement_summary"]
    assert "expand_candidates" in summary
    assert "review_candidates" in summary
    assert "next_hypothesis" in summary
