"""決定論的なルールベース生成（Layer 3の最終フォールバック）。

LLM・事前生成済み回答のいずれも使えない場合でも、Step 1〜6のデモフローを
必ず完走できるようにする最後のフォールバックであり、常に成功する。
"""

from __future__ import annotations

from datetime import date

from backend.config import GENERATION_MODE_LABEL, GENERATION_MODE_RULE_BASED, current_timestamp

RULE_BASED_MODEL_VERSION = "rule-based-v1"

ACTION_EC_REVISIT = "EC再利用の案内"
ACTION_QR_BENEFIT = "QR決済の利用メリット案内"
ACTION_CARD_BENEFIT = "カード利用特典の案内"
ACTION_CROSS_SERVICE = "複数サービスをまたぐ軽量なポイント施策"
ACTION_WATCH = "施策を行わず経過観察"

DECLINE_THRESHOLD_PCT = -10.0

DOC_TITLES = {
    "kb-ec-revisit": "EC再訪促進メールの施策概要",
    "kb-qr-incentive": "QR決済ポイント還元施策の概要",
    "kb-card-benefit": "カード利用特典案内の施策概要",
    "kb-cross-service": "複数サービス横断ポイント施策の概要",
    "kb-service-overview": "サービス情報（EC・QR決済・カード・ネット銀行・ポイント）",
    "kb-support-policy": "顧客対応方針",
}


def _reference(doc_id: str) -> dict:
    return {"doc_id": doc_id, "title": DOC_TITLES.get(doc_id, doc_id), "type": "knowledge"}


def _build_summary(customer: dict, prediction: dict) -> str:
    display_name = customer["display_name"]
    risk_label = prediction["risk_band_label"]
    probability_pct = round(prediction["churn_probability"] * 100)
    top_reason = prediction["reasons"][0] if prediction["reasons"] else "特筆すべき変化はありません"
    return f"{display_name}は休眠確率{probability_pct}%（{risk_label}リスク）。{top_reason}。"


def _has_recent_campaign(customer: dict, prediction: dict, within_days: int = 30) -> bool:
    campaigns = customer.get("campaigns", [])
    if not campaigns:
        return False
    reference_date = date.fromisoformat(prediction["inference_at"][:10])
    for campaign in campaigns:
        sent_date = date.fromisoformat(campaign["sent_date"])
        if (reference_date - sent_date).days <= within_days:
            return True
    return False


def generate_rule_based(context: dict) -> dict:
    customer = context["customer"]
    prediction = context["prediction"]
    services = customer["services"]

    candidates: list[tuple[float, str, str, str]] = []  # (magnitude, title, reason, doc_id)

    service_drop = customer["previous_service_count"] - customer["service_count"]
    if service_drop >= 1:
        candidates.append(
            (
                0.9,
                ACTION_CROSS_SERVICE,
                (
                    f"利用サービス数が{customer['previous_service_count']}"
                    f"→{customer['service_count']}に減少しているため、"
                    "複数サービスをまたぐ軽量なポイント施策が候補になります"
                    "（過度に高額な施策は前提としません）。"
                ),
                "kb-cross-service",
            )
        )

    ec_pct = services.get("ec", {}).get("period_change_pct")
    if ec_pct is not None and ec_pct <= DECLINE_THRESHOLD_PCT:
        candidates.append(
            (
                abs(ec_pct) / 100,
                ACTION_EC_REVISIT,
                f"ECの購入額が前期比{ec_pct:.0f}%低下しているため、再利用を促す案内が候補になります。",
                "kb-ec-revisit",
            )
        )

    qr_pct = services.get("qr", {}).get("period_change_pct")
    if qr_pct is not None and qr_pct <= DECLINE_THRESHOLD_PCT:
        candidates.append(
            (
                abs(qr_pct) / 100,
                ACTION_QR_BENEFIT,
                f"QR決済の利用額が前期比{qr_pct:.0f}%低下しているため、利用メリットの案内が候補になります。",
                "kb-qr-incentive",
            )
        )

    card_pct = services.get("card", {}).get("period_change_pct")
    if card_pct is not None and card_pct <= DECLINE_THRESHOLD_PCT:
        candidates.append(
            (
                abs(card_pct) / 100,
                ACTION_CARD_BENEFIT,
                f"カードの利用額が前期比{card_pct:.0f}%低下しているため、利用特典の案内が候補になります。",
                "kb-card-benefit",
            )
        )

    # 高リスクでも一律に施策を行うロジックにしないため、対象アクションは最大2件に絞り、
    # 残り1枠は必ず「施策を行わず経過観察」に確保する。
    candidates.sort(key=lambda c: c[0], reverse=True)
    top_candidates = candidates[:2]

    actions = [{"title": title, "reason": reason} for _, title, reason, _ in top_candidates]
    reference_doc_ids = [doc_id for _, _, _, doc_id in top_candidates]

    if _has_recent_campaign(customer, prediction):
        watch_reason = "直近で施策を配信済みのため、効果を見極める期間として経過観察も選択肢です。"
    elif not candidates:
        watch_reason = "直近の利用状況は安定しており、追加施策を行わず経過観察する選択肢です。"
    else:
        watch_reason = "推奨アクションの効果を保証するものではないため、見送り（経過観察）も有効な選択です。"

    actions.append({"title": ACTION_WATCH, "reason": watch_reason})
    reference_doc_ids.append("kb-support-policy")

    cautions = [
        "本推奨は過去データに基づく参考情報であり、効果を保証するものではありません。",
        "実施の可否は担当者の判断に基づき、自動配信は行いません。",
    ]

    seen: set[str] = set()
    references = []
    for doc_id in reference_doc_ids:
        if doc_id not in seen:
            seen.add(doc_id)
            references.append(_reference(doc_id))

    return {
        "customer_id": context["customer_id"],
        "generation_mode": GENERATION_MODE_RULE_BASED,
        "generation_mode_label": GENERATION_MODE_LABEL[GENERATION_MODE_RULE_BASED],
        "model_version": RULE_BASED_MODEL_VERSION,
        "generated_at": current_timestamp(),
        "summary": _build_summary(customer, prediction),
        "actions": actions[:3],
        "cautions": cautions,
        "references": references,
    }
