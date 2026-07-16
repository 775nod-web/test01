"""顧客360・予測・社内ナレッジを統合した、推奨アクション生成用のコンテキスト作成。

LLM・事前生成済み回答・ルールベースのいずれの生成方式でも、同じコンテキストを
入力として受け取ることで、生成方式が変わっても参照するデータの一貫性を保つ。
"""

from __future__ import annotations

from typing import Optional

from backend.services.customer_service import CustomerNotFoundError
from backend.services.data_source import CustomerDataset, load_customer_dataset
from backend.services.knowledge_base import select_relevant_docs


def build_recommendation_context(
    customer_id: str, dataset: Optional[CustomerDataset] = None
) -> dict:
    """指定顧客の推奨アクション生成用コンテキストを組み立てる。

    存在しないcustomer_idの場合はCustomerNotFoundErrorを送出する。
    """
    dataset = dataset if dataset is not None else load_customer_dataset()

    customer = dataset.customers_by_id.get(customer_id)
    prediction = dataset.predictions_by_id.get(customer_id)
    if customer is None or prediction is None:
        raise CustomerNotFoundError(customer_id)

    knowledge_docs = select_relevant_docs()

    return {
        "customer_id": customer_id,
        "customer": customer,
        "prediction": prediction,
        "knowledge_docs": knowledge_docs,
        "data_mode": dataset.data_mode,
        "model_mode": dataset.model_mode,
        "updated_at": dataset.updated_at,
    }
