"""施策結果から次の推奨アクションを決定するルールベースのテスト。"""

from __future__ import annotations

from backend.services.feedback_action_service import (
    ACTION_TYPE_CHANGE_CHANNEL,
    ACTION_TYPE_CHANGE_OFFER,
    ACTION_TYPE_CONTINUE_OBSERVATION,
    ACTION_TYPE_EXPAND,
    ACTION_TYPE_REVIEW_TARGETING,
    determine_next_action,
)


def test_engaged_and_recovered_returns_expand() -> None:
    result = determine_next_action(
        decision="approved",
        selected_action="クーポン利用の案内",
        comment=None,
        campaign_status="実施済み",
        customer_response="クーポン利用",
        usage_recovery_status="30日以内に利用再開",
    )
    assert result["type"] == ACTION_TYPE_EXPAND


def test_engaged_and_not_recovered_returns_change_offer() -> None:
    result = determine_next_action(
        decision="approved",
        selected_action=None,
        comment=None,
        campaign_status="実施済み",
        customer_response="クーポン利用",
        usage_recovery_status="利用再開なし",
    )
    assert result["type"] == ACTION_TYPE_CHANGE_OFFER


def test_not_engaged_and_not_recovered_returns_change_channel() -> None:
    result = determine_next_action(
        decision="approved",
        selected_action=None,
        comment=None,
        campaign_status="実施済み",
        customer_response="反応なし",
        usage_recovery_status="利用再開なし",
    )
    assert result["type"] == ACTION_TYPE_CHANGE_CHANNEL


def test_skipped_decision_returns_review_targeting_regardless_of_outcome() -> None:
    result = determine_next_action(
        decision="skipped",
        selected_action=None,
        comment="今回は見送り",
        campaign_status="実施済み",
        customer_response="クーポン利用",
        usage_recovery_status="30日以内に利用再開",
    )
    assert result["type"] == ACTION_TYPE_REVIEW_TARGETING
    assert "今回は見送り" in result["reason"]


def test_observing_period_returns_continue_observation() -> None:
    result = determine_next_action(
        decision=None,
        selected_action=None,
        comment=None,
        campaign_status="実施済み",
        customer_response="問い合わせ",
        usage_recovery_status="観測期間中",
    )
    assert result["type"] == ACTION_TYPE_CONTINUE_OBSERVATION


def test_unknown_values_do_not_raise_and_return_fallback() -> None:
    result = determine_next_action(
        decision="unexpected-value",
        selected_action=None,
        comment=None,
        campaign_status="",
        customer_response="",
        usage_recovery_status="",
    )
    assert result["type"]
    assert result["reason"]
    assert result["next_review_timing"]


def test_missing_values_do_not_raise() -> None:
    result = determine_next_action(
        decision=None,
        selected_action=None,
        comment=None,
        campaign_status="実施済み",
        customer_response=None,  # type: ignore[arg-type]
        usage_recovery_status=None,  # type: ignore[arg-type]
    )
    assert result["type"]


def test_same_input_returns_same_result_every_time() -> None:
    kwargs = dict(
        decision="approved",
        selected_action="クーポン利用の案内",
        comment=None,
        campaign_status="実施済み",
        customer_response="クーポン利用",
        usage_recovery_status="30日以内に利用再開",
    )
    first = determine_next_action(**kwargs)
    second = determine_next_action(**kwargs)
    assert first == second
