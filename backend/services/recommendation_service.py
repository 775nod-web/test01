"""推奨アクション生成の切り替え（Layer 3）。

実行優先順位：
    1. 設定済みの実LLMエンドポイント
    2. 事前生成済みLLM回答
    3. 決定論的なルールベース生成（常に成功する最終フォールバック）

いずれの方式でも、参照するデータ（顧客360・予測・社内ナレッジ）は
`recommendation_context.build_recommendation_context` が組み立てた同じコンテキストを使う。
"""

from __future__ import annotations

import logging
from typing import Optional

from backend.config import resolve_llm_config
from backend.services.data_source import CustomerDataset
from backend.services.llm_client import LLMOutputInvalidError, LLMRequestError, generate as call_llm
from backend.services.pre_generated_store import load_pre_generated_recommendation
from backend.services.recommendation_context import build_recommendation_context
from backend.services.rule_based_generator import generate_rule_based

logger = logging.getLogger(__name__)


def get_recommendation(customer_id: str, dataset: Optional[CustomerDataset] = None) -> dict:
    """指定顧客の推奨アクションを生成する。存在しない顧客はCustomerNotFoundErrorを送出する。"""
    context = build_recommendation_context(customer_id, dataset=dataset)

    llm_config = resolve_llm_config()
    if llm_config is not None:
        try:
            return call_llm(context, llm_config)
        except (LLMRequestError, LLMOutputInvalidError) as exc:
            # 技術的な詳細や秘密情報は画面・詳細ログへ出さず、フォールバックすることのみ記録する。
            logger.warning(
                "LLM生成に失敗したため事前生成済み回答へフォールバックします（customer_id=%s, reason=%s）",
                customer_id,
                type(exc).__name__,
            )

    pre_generated = load_pre_generated_recommendation(customer_id)
    if pre_generated is not None:
        return pre_generated

    return generate_rule_based(context)
