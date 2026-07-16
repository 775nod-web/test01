"""保存済みの判断からフィードバック概要を集計する（Layer 4のフィードバックループ）。

実際の自動再学習・自動施策改善はこのフェーズでは実装しない（本番化時に追加）。
ここでは、判断が記録され、承認・修正・見送りの集計へ確実に反映されることまでを扱う。
"""

from __future__ import annotations

from typing import Optional

from backend.config import GENERATION_MODE_LABEL, current_timestamp
from backend.services.data_source import CustomerDataset, load_customer_dataset
from backend.services.decision_store import get_decision_store
from backend.services.feedback_action_service import build_improvement_summary, determine_next_action
from backend.services.sample_outcomes import load_sample_outcomes

RECENT_DECISIONS_LIMIT = 10


def build_feedback_summary(
    dataset: Optional[CustomerDataset] = None, decisions: Optional[list[dict]] = None
) -> dict:
    dataset = dataset if dataset is not None else load_customer_dataset()

    store = get_decision_store()
    decisions = decisions if decisions is not None else store.list_decisions()

    approved_count = sum(1 for d in decisions if d["decision"] == "approved")
    modified_count = sum(1 for d in decisions if d["decision"] == "modified")
    skipped_count = sum(1 for d in decisions if d["decision"] == "skipped")

    by_generation_mode: dict[str, int] = {}
    for decision in decisions:
        mode = decision.get("generation_mode") or "unknown"
        by_generation_mode[mode] = by_generation_mode.get(mode, 0) + 1

    recent = sorted(decisions, key=lambda d: d["decided_at"], reverse=True)[:RECENT_DECISIONS_LIMIT]
    recent_decisions = []
    for decision in recent:
        customer = dataset.customers_by_id.get(decision["customer_id"])
        display_name = customer["display_name"] if customer else decision["customer_id"]
        generation_mode = decision.get("generation_mode")
        recent_decisions.append(
            {
                "customer_id": decision["customer_id"],
                "display_name": display_name,
                "decision": decision["decision"],
                "selected_action": decision.get("selected_action"),
                "decided_at": decision["decided_at"],
                "generation_mode_label": GENERATION_MODE_LABEL.get(generation_mode, generation_mode),
            }
        )

    latest_decision_by_customer: dict[str, dict] = {}
    for decision in sorted(decisions, key=lambda d: d["decided_at"]):
        latest_decision_by_customer[decision["customer_id"]] = decision

    sample_outcomes = []
    for outcome in load_sample_outcomes():
        customer_id = outcome["customer_id"]
        customer = dataset.customers_by_id.get(customer_id)
        display_name = customer["display_name"] if customer else customer_id
        matched_decision = latest_decision_by_customer.get(customer_id)
        decision_value = matched_decision["decision"] if matched_decision else None
        selected_action = matched_decision.get("selected_action") if matched_decision else None
        comment = matched_decision.get("comment") if matched_decision else None

        recommended_next_action = determine_next_action(
            decision=decision_value,
            selected_action=selected_action,
            comment=comment,
            campaign_status=outcome["campaign_status"],
            customer_response=outcome["customer_response"],
            usage_recovery_status=outcome["usage_recovery_status"],
        )

        sample_outcomes.append(
            {
                "customer_id": customer_id,
                "display_name": display_name,
                "campaign_status": outcome["campaign_status"],
                "customer_response": outcome["customer_response"],
                "usage_recovery_status": outcome["usage_recovery_status"],
                "observed_at": outcome["observed_at"],
                "is_sample": True,
                "decision": decision_value,
                "selected_action": selected_action,
                "comment": comment,
                "decided_at": matched_decision.get("decided_at") if matched_decision else None,
                "recommended_next_action": recommended_next_action,
            }
        )

    improvement_summary = build_improvement_summary(sample_outcomes)

    return {
        "total_decisions": len(decisions),
        "approved_count": approved_count,
        "modified_count": modified_count,
        "skipped_count": skipped_count,
        "by_generation_mode": by_generation_mode,
        "recent_decisions": recent_decisions,
        "sample_outcomes": sample_outcomes,
        "improvement_summary": improvement_summary,
        "updated_at": current_timestamp(),
        "storage_mode": store.storage_mode,
        "persisted": store.persisted,
    }
