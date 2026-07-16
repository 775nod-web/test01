"""顧客一覧・詳細のレスポンス組み立て。

顧客360（customer360.json）と休眠予測（predictions.json）を customer_id で結合する。
「予測結果が顧客360を参照している」「推奨結果が顧客360と予測結果を参照している」という
受け入れ条件に対応するため、両者は常に customer_id をキーに結合してから返す。
"""

from __future__ import annotations

from typing import Optional

from backend.services.data_source import CustomerDataset, load_customer_dataset


class CustomerNotFoundError(Exception):
    def __init__(self, customer_id: str) -> None:
        self.customer_id = customer_id
        super().__init__(f"customer_id '{customer_id}' が見つかりません。")


def _customer_summary(customer: dict, prediction: dict) -> dict:
    reasons = prediction.get("reasons") or []
    return {
        "customer_id": customer["customer_id"],
        "display_name": customer["display_name"],
        "risk_band": prediction["risk_band"],
        "risk_band_label": prediction["risk_band_label"],
        "churn_probability": prediction["churn_probability"],
        "service_count": customer["service_count"],
        "previous_service_count": customer["previous_service_count"],
        "top_reason": reasons[0] if reasons else None,
    }


def list_customers(dataset: Optional[CustomerDataset] = None) -> dict:
    dataset = dataset if dataset is not None else load_customer_dataset()

    summaries = []
    for customer_id, customer in dataset.customers_by_id.items():
        prediction = dataset.predictions_by_id.get(customer_id)
        if prediction is None:
            continue
        summaries.append(_customer_summary(customer, prediction))

    # 対応の優先度が伝わるよう、休眠確率が高い順に並べる
    summaries.sort(key=lambda s: s["churn_probability"], reverse=True)

    return {
        "data_mode": dataset.data_mode,
        "model_mode": dataset.model_mode,
        "updated_at": dataset.updated_at,
        "customers": summaries,
    }


def get_customer_detail(customer_id: str, dataset: Optional[CustomerDataset] = None) -> dict:
    dataset = dataset if dataset is not None else load_customer_dataset()

    customer = dataset.customers_by_id.get(customer_id)
    prediction = dataset.predictions_by_id.get(customer_id)
    if customer is None or prediction is None:
        raise CustomerNotFoundError(customer_id)

    return {
        "data_mode": dataset.data_mode,
        "model_mode": dataset.model_mode,
        "updated_at": dataset.updated_at,
        "customer": customer,
        "prediction": prediction,
    }
