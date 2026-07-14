"""PoC & Future Expansion page. Mostly static, labeled content — see
docs/poc-success-criteria.md and docs/free-edition-limitations.md, which
this mirrors. The one live element is a small cross-sell reuse sample."""

from __future__ import annotations

from backend.db import QueryEngine

SYNTHETIC_ELEMENTS = [
    "All customers, accounts, cards, app activity, contacts, products, and "
    "campaigns are synthetically generated with a fixed random seed — no "
    "real bank or customer data exists anywhere in this demo.",
    "simulated_annual_value and estimated_value_at_risk are labeled "
    "simulated proxies, not real financial figures.",
    "churn_label_90d is a simulated ground-truth label for optional "
    "Phase 7 ML validation only — the mandatory rule-based score never "
    "reads it.",
]

MUST_VALIDATE_WITH_BANK_DATA = [
    "Whether the same 8 signals (balance decline, card spend decline, app "
    "usage decline, long inactivity, complaints, unresolved contacts, "
    "stopped salary deposit, product decline) are available and reliable "
    "in real source systems, at the same refresh cadence.",
    "Whether the point weights and High/Medium/Low thresholds in "
    "docs/risk-scoring.md hold up against real churn outcomes, or need "
    "recalibration per portfolio/segment.",
    "Whether simulated_annual_value should be replaced with an actual "
    "profitability or relationship-value metric from finance systems.",
    "Data quality and completeness of real source systems (nulls, "
    "duplicates, latency) — Bronze/Silver cleaning rules will need to be "
    "revisited for real-world messiness.",
    "Actual capacity and cost of the retention channels (call center, "
    "push/app, email) referenced in the action mapping.",
]

POC_SUCCESS_METRICS = [
    "Lift: retention/response rate of the prioritized audience vs. today's "
    "broad campaign audience, measured over a real campaign cycle.",
    "Driver stability: whether the same primary drivers keep recurring "
    "for the same customers month over month, or churn noisily.",
    "Stakeholder adoption: whether marketing/CRM leaders actually use the "
    "Customer 360 + driver explanation to select an action, versus "
    "reverting to broad campaigns.",
    "Operational fit: whether the recommended actions map cleanly onto "
    "real call-center/app/email workflows without new tooling.",
    "False-positive rate: share of flagged High-risk customers who show "
    "no real-world churn behavior in the following quarter.",
]

FREE_EDITION_LIMITATIONS = [
    "No real bank source-system connectivity.",
    "No automatic hand-off to external marketing platforms.",
    "No real-time/streaming inference — batch only.",
    "No fully automated Next Best Action — every recommendation requires "
    "human review before customer contact.",
    "No production-grade model-serving requirement (rule-based score is "
    "computed in batch SQL).",
    "Free Edition itself: serverless-only compute, a single 2X-Small SQL "
    "warehouse, fair-use quotas, no SLA, and Databricks Apps may auto-stop "
    "after 24 hours of inactivity.",
]

CROSS_SELL_REUSE_NOTE = (
    "The same Customer 360 table used for retention (value, tenure, "
    "product holdings, engagement, complaints) generalizes directly to a "
    "cross-sell audience: low-risk, engaged customers with few products "
    "are a plausible next-best-offer audience. This is shown as one "
    "illustrative query below, not a second demo — see CLAUDE.md's fixed "
    "storyline."
)


def get_poc_summary(engine: QueryEngine) -> dict:
    cross_sell_sample = engine.run("cross_sell_opportunity.sql", limit=10)
    return {
        "synthetic_elements": SYNTHETIC_ELEMENTS,
        "must_validate_with_bank_data": MUST_VALIDATE_WITH_BANK_DATA,
        "poc_success_metrics": POC_SUCCESS_METRICS,
        "free_edition_limitations": FREE_EDITION_LIMITATIONS,
        "cross_sell_reuse_note": CROSS_SELL_REUSE_NOTE,
        "cross_sell_sample": cross_sell_sample,
    }
