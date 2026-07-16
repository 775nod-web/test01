"""設定済みの実LLMエンドポイントを呼び出すクライアント（Layer 3の主経路）。

接続情報・モデル名・認証情報は `backend/config.py` の `resolve_llm_config()` が
環境変数から読み取るのみで、コードへ直接記載しない。呼び出しにはタイムアウトと
再試行上限を設け、出力はスキーマ検証してから利用する。検証に失敗した場合や
呼び出し自体が失敗した場合は例外を送出し、呼び出し側で次の生成方式（事前生成済み
回答 → ルールベース）へフォールバックする。

失敗時の詳細な例外内容や、リクエストヘッダー・レスポンス本文などの秘密情報に
つながりうる内容はログへ出力しない。
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from backend.config import GENERATION_MODE_LABEL, GENERATION_MODE_LLM, LLMConfig, current_timestamp

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "あなたは顧客維持担当者向けの社内アシスタントです。"
    "与えられた顧客360・休眠予測・過去施策・顧客対応方針・社内ナレッジのみを根拠に、"
    "次のアクション候補を提案してください。"
    "出力は必ず次のキーを持つJSONのみとし、他の文章を含めないでください: "
    "summary（顧客状況の要約、日本語、300字以内）, "
    "actions（最大3件の配列。各要素はtitleとreasonを持つ）, "
    "cautions（注意事項の配列）, "
    "references（根拠として使った社内ナレッジのdoc_idの配列。渡された候補以外のIDは使わないこと）。"
    "特定のアクションを必ず実施すべきと断定せず、"
    "「施策を行わず経過観察」も有効な候補として検討してください。"
    "効果を保証する表現や、過度に高額なインセンティブは避けてください。"
)


class LLMRequestError(RuntimeError):
    """LLM呼び出し自体が失敗した場合（タイムアウト・通信エラー等）。"""


class LLMOutputInvalidError(RuntimeError):
    """LLMの出力がスキーマ検証に失敗した場合（不正な形式・許可されない参照元等）。"""


def _build_user_payload(context: dict) -> dict:
    customer = context["customer"]
    prediction = context["prediction"]
    return {
        "customer": {
            "display_name": customer["display_name"],
            "service_count": customer["service_count"],
            "previous_service_count": customer["previous_service_count"],
            "services": customer["services"],
            "combined_qr_card": customer["combined_qr_card"],
            "campaigns": customer["campaigns"],
            "support_summary": customer["support_summary"],
        },
        "prediction": {
            "risk_band": prediction["risk_band"],
            "risk_band_label": prediction["risk_band_label"],
            "churn_probability": prediction["churn_probability"],
            "reasons": prediction["reasons"],
        },
        "knowledge_docs": [
            {"doc_id": doc["doc_id"], "title": doc["title"], "body": doc["body"]}
            for doc in context["knowledge_docs"]
        ],
    }


def _call_endpoint(llm_config: LLMConfig, payload: dict) -> dict:
    """LLMエンドポイントへHTTP POSTする（モックしやすいよう分離した関数）。"""
    headers = {
        "Authorization": f"Bearer {llm_config.api_key}",
        "Content-Type": "application/json",
    }
    body: dict[str, Any] = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
    }
    if llm_config.model:
        body["model"] = llm_config.model

    response = httpx.post(
        llm_config.endpoint_url,
        headers=headers,
        json=body,
        timeout=llm_config.timeout_seconds,
    )
    response.raise_for_status()
    data = response.json()
    content = data["choices"][0]["message"]["content"]
    return json.loads(content)


def _validate_output(raw: Any, allowed_doc_ids: set[str]) -> dict:
    if not isinstance(raw, dict):
        raise LLMOutputInvalidError("LLM出力がオブジェクト形式ではありません。")

    summary = raw.get("summary")
    if not isinstance(summary, str) or not (0 < len(summary) <= 400):
        raise LLMOutputInvalidError("summaryが不正です。")

    actions = raw.get("actions")
    if not isinstance(actions, list) or not (1 <= len(actions) <= 3):
        raise LLMOutputInvalidError("actionsが不正です（1〜3件である必要があります）。")
    for action in actions:
        if not isinstance(action, dict):
            raise LLMOutputInvalidError("actionsの要素が不正です。")
        title = action.get("title")
        reason = action.get("reason")
        if not isinstance(title, str) or not (0 < len(title) <= 80):
            raise LLMOutputInvalidError("actionのtitleが不正です。")
        if not isinstance(reason, str) or not (0 < len(reason) <= 300):
            raise LLMOutputInvalidError("actionのreasonが不正です。")

    cautions = raw.get("cautions", [])
    if not isinstance(cautions, list) or any(not isinstance(c, str) for c in cautions):
        raise LLMOutputInvalidError("cautionsが不正です。")

    references = raw.get("references", [])
    if not isinstance(references, list):
        raise LLMOutputInvalidError("referencesが不正です。")

    reference_doc_ids: list[str] = []
    for ref in references:
        if isinstance(ref, str):
            doc_id = ref
        elif isinstance(ref, dict):
            doc_id = ref.get("doc_id")
        else:
            raise LLMOutputInvalidError("referencesの要素が不正です。")
        if doc_id not in allowed_doc_ids:
            raise LLMOutputInvalidError("referencesに許可されていない文書IDが含まれています。")
        reference_doc_ids.append(doc_id)

    return {
        "summary": summary,
        "actions": actions[:3],
        "cautions": cautions,
        "reference_doc_ids": reference_doc_ids,
    }


def generate(context: dict, llm_config: LLMConfig) -> dict:
    """実LLMエンドポイントを呼び出し、検証済みの推奨結果を返す。

    呼び出し・検証のいずれかに失敗した場合はLLMRequestErrorまたは
    LLMOutputInvalidErrorを送出する。呼び出し側（recommendation_service）で
    捕捉し、次の生成方式へフォールバックすることを想定する。
    """
    doc_by_id = {doc["doc_id"]: doc for doc in context["knowledge_docs"]}
    allowed_doc_ids = set(doc_by_id.keys())
    payload = _build_user_payload(context)

    last_error: Exception | None = None
    attempts = llm_config.max_retries + 1
    for _ in range(attempts):
        try:
            raw_output = _call_endpoint(llm_config, payload)
            validated = _validate_output(raw_output, allowed_doc_ids)
            references = [
                {
                    "doc_id": doc_id,
                    "title": doc_by_id[doc_id]["title"],
                    "type": "knowledge",
                }
                for doc_id in validated["reference_doc_ids"]
            ]
            return {
                "customer_id": context["customer_id"],
                "generation_mode": GENERATION_MODE_LLM,
                "generation_mode_label": GENERATION_MODE_LABEL[GENERATION_MODE_LLM],
                "model_version": llm_config.model or "unknown",
                "generated_at": current_timestamp(),
                "summary": validated["summary"],
                "actions": validated["actions"],
                "cautions": validated["cautions"],
                "references": references,
            }
        except LLMOutputInvalidError as exc:
            logger.warning("LLM出力の検証に失敗したため、フォールバックします: %s", type(exc).__name__)
            last_error = exc
            break  # 出力形式の問題は再試行しても解決しないため即座に打ち切る
        except (httpx.TimeoutException, httpx.HTTPError, KeyError, ValueError) as exc:
            logger.warning("LLM呼び出しに失敗したため再試行します: %s", type(exc).__name__)
            last_error = exc
            continue

    raise LLMRequestError("LLM呼び出しに失敗しました。") from last_error
