"""実LLM呼び出しのタイムアウト・再試行・出力検証を、HTTP層をモックして検証する。"""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from backend.config import LLMConfig
from backend.services import llm_client
from backend.services.recommendation_context import build_recommendation_context


@pytest.fixture
def context() -> dict:
    return build_recommendation_context("C059")


@pytest.fixture
def llm_config() -> LLMConfig:
    return LLMConfig(
        endpoint_url="https://example.invalid/llm",
        api_key="dummy-key",
        model="dummy-model",
        timeout_seconds=1.0,
        max_retries=1,
    )


def test_generate_returns_llm_result_on_success(context: dict, llm_config: LLMConfig) -> None:
    valid_output = {
        "summary": "テスト要約です。",
        "actions": [{"title": "施策を行わず経過観察", "reason": "テスト理由"}],
        "cautions": ["テスト注意事項"],
        "references": ["kb-support-policy"],
    }
    with patch.object(llm_client, "_call_endpoint", return_value=valid_output):
        result = llm_client.generate(context, llm_config)

    assert result["generation_mode"] == "llm"
    assert result["summary"] == "テスト要約です。"
    assert result["references"] == [
        {"doc_id": "kb-support-policy", "title": "顧客対応方針", "type": "knowledge"}
    ]


def test_generate_raises_on_timeout_after_retries(context: dict, llm_config: LLMConfig) -> None:
    with patch.object(llm_client, "_call_endpoint", side_effect=httpx.TimeoutException("timeout")) as mock_call:
        with pytest.raises(llm_client.LLMRequestError):
            llm_client.generate(context, llm_config)

    # 初回 + 再試行1回 = 2回呼び出されること
    assert mock_call.call_count == llm_config.max_retries + 1


def test_generate_raises_on_invalid_output_without_retrying(
    context: dict, llm_config: LLMConfig
) -> None:
    invalid_output = {"summary": "", "actions": [], "cautions": [], "references": []}
    with patch.object(llm_client, "_call_endpoint", return_value=invalid_output) as mock_call:
        with pytest.raises(llm_client.LLMRequestError) as excinfo:
            llm_client.generate(context, llm_config)

    assert isinstance(excinfo.value.__cause__, llm_client.LLMOutputInvalidError)
    # 出力形式の不正は再試行しても解決しないため、1回で打ち切ること
    assert mock_call.call_count == 1


def test_generate_rejects_hallucinated_reference_doc_id(
    context: dict, llm_config: LLMConfig
) -> None:
    hallucinated_output = {
        "summary": "テスト",
        "actions": [{"title": "EC再利用の案内", "reason": "テスト"}],
        "cautions": [],
        "references": ["kb-does-not-exist"],
    }
    with patch.object(llm_client, "_call_endpoint", return_value=hallucinated_output):
        with pytest.raises(llm_client.LLMRequestError) as excinfo:
            llm_client.generate(context, llm_config)

    assert isinstance(excinfo.value.__cause__, llm_client.LLMOutputInvalidError)


def test_generate_rejects_too_many_actions(context: dict, llm_config: LLMConfig) -> None:
    too_many_actions = {
        "summary": "テスト",
        "actions": [
            {"title": "A", "reason": "1"},
            {"title": "B", "reason": "2"},
            {"title": "C", "reason": "3"},
            {"title": "D", "reason": "4"},
        ],
        "cautions": [],
        "references": [],
    }
    with patch.object(llm_client, "_call_endpoint", return_value=too_many_actions):
        with pytest.raises(llm_client.LLMRequestError):
            llm_client.generate(context, llm_config)
