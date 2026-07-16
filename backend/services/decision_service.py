"""判断（承認／修正／見送り）の保存ロジック。"""

from __future__ import annotations

from typing import Optional

from backend.config import current_timestamp
from backend.services.customer_service import CustomerNotFoundError
from backend.services.data_source import CustomerDataset, load_customer_dataset
from backend.services.decision_store import get_decision_store


def save_decision(
    customer_id: str, decision_input: dict, dataset: Optional[CustomerDataset] = None
) -> dict:
    dataset = dataset if dataset is not None else load_customer_dataset()
    if customer_id not in dataset.customers_by_id:
        raise CustomerNotFoundError(customer_id)

    record = {
        "customer_id": customer_id,
        "decision": decision_input["decision"],
        "selected_action": decision_input.get("selected_action"),
        "modified_text": decision_input.get("modified_text"),
        "comment": decision_input.get("comment"),
        "decided_at": current_timestamp(),
        "generation_mode": decision_input.get("generation_mode"),
        "model_version": decision_input.get("model_version"),
    }

    store = get_decision_store()
    return store.save_decision(record)
