"""LLM → 事前生成済み回答 → ルールベースの切り替えを検証する。"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.config import LLMConfig
from backend.services import recommendation_service
from backend.services.customer_service import CustomerNotFoundError
from backend.services.llm_client import LLMRequestError

PRE_GENERATED_CUSTOMER_ID = "C059"  # scripts/generate_pregenerated_recommendations.py に含まれる顧客
RULE_BASED_ONLY_CUSTOMER_ID = "C002"  # 事前生成済みフィクスチャに含まれない顧客


def test_uses_pre_generated_when_llm_not_configured() -> None:
    with patch.object(recommendation_service, "resolve_llm_config", return_value=None):
        result = recommendation_service.get_recommendation(PRE_GENERATED_CUSTOMER_ID)

    assert result["generation_mode"] == "pre_generated"


def test_uses_rule_based_when_no_llm_and_no_pre_generated_fixture() -> None:
    with patch.object(recommendation_service, "resolve_llm_config", return_value=None):
        result = recommendation_service.get_recommendation(RULE_BASED_ONLY_CUSTOMER_ID)

    assert result["generation_mode"] == "rule_based"
    assert 1 <= len(result["actions"]) <= 3


def test_uses_llm_when_configured_and_successful() -> None:
    dummy_config = LLMConfig(
        endpoint_url="https://example.invalid/llm",
        api_key="k",
        model="m",
        timeout_seconds=1.0,
        max_retries=1,
    )
    llm_result = {
        "customer_id": RULE_BASED_ONLY_CUSTOMER_ID,
        "generation_mode": "llm",
        "generation_mode_label": "LLM生成",
        "model_version": "m",
        "generated_at": "2026-07-16T00:00:00+00:00",
        "summary": "LLM要約",
        "actions": [{"title": "施策を行わず経過観察", "reason": "理由"}],
        "cautions": [],
        "references": [],
    }
    with patch.object(recommendation_service, "resolve_llm_config", return_value=dummy_config):
        with patch.object(recommendation_service, "call_llm", return_value=llm_result):
            result = recommendation_service.get_recommendation(RULE_BASED_ONLY_CUSTOMER_ID)

    assert result["generation_mode"] == "llm"
    assert result["summary"] == "LLM要約"


def test_falls_back_to_pre_generated_when_llm_fails() -> None:
    dummy_config = LLMConfig(
        endpoint_url="https://example.invalid/llm",
        api_key="k",
        model="m",
        timeout_seconds=1.0,
        max_retries=1,
    )
    with patch.object(recommendation_service, "resolve_llm_config", return_value=dummy_config):
        with patch.object(recommendation_service, "call_llm", side_effect=LLMRequestError("failed")):
            result = recommendation_service.get_recommendation(PRE_GENERATED_CUSTOMER_ID)

    assert result["generation_mode"] == "pre_generated"


def test_falls_back_to_rule_based_when_llm_fails_and_no_pre_generated_fixture() -> None:
    dummy_config = LLMConfig(
        endpoint_url="https://example.invalid/llm",
        api_key="k",
        model="m",
        timeout_seconds=1.0,
        max_retries=1,
    )
    with patch.object(recommendation_service, "resolve_llm_config", return_value=dummy_config):
        with patch.object(recommendation_service, "call_llm", side_effect=LLMRequestError("failed")):
            result = recommendation_service.get_recommendation(RULE_BASED_ONLY_CUSTOMER_ID)

    assert result["generation_mode"] == "rule_based"


def test_raises_not_found_for_unknown_customer() -> None:
    with pytest.raises(CustomerNotFoundError):
        recommendation_service.get_recommendation("NOPE")
