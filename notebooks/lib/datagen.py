"""
Deterministic synthetic data generator for the digital-bank customer
retention demo (see CLAUDE.md / PHASES_01_TO_04.md, Phase 2).

Pure Python, stdlib only, so it can be unit-tested (tests/test_datagen.py)
without Spark or a Databricks workspace. The Databricks notebook
notebooks/01_generate_synthetic_data.py imports this module and converts
its outputs into Spark DataFrames written as Bronze Delta tables.

All identifiers, names, and values are synthetic. No real-looking account
numbers, card numbers, addresses, or personal identifiers are generated.
Every "value"/"churn label" figure is a simulated placeholder, not a real
business metric.
"""

from __future__ import annotations

import calendar
import random
from dataclasses import dataclass
from datetime import date

SEED = 42
REFERENCE_DATE = date(2026, 6, 30)  # fixed anchor: the "current" month-end
NUM_MONTHS = 12

ARCHETYPES = [
    ("stable_low_risk", 0.45),
    ("declining_balance", 0.15),
    ("disengaging", 0.15),
    ("service_issues", 0.10),
    ("salary_stopped", 0.07),
    ("strong_retention", 0.08),
]

# Forced archetypes guarantee specific Risk Segment x Value Segment
# combinations exist in every generated population (CLAUDE.md remediation
# Fix 1) instead of leaving them to weighted-random chance. CUST000001
# (generation index 0) is always the first FORCED_HIGH_RISK_HIGH_VALUE slot
# — the fixed demo customer referenced throughout the app and docs.
FORCED_HIGH_RISK_HIGH_VALUE = "forced_high_risk_high_value"
FORCED_HIGH_RISK_MEDIUM_VALUE = "forced_high_risk_medium_value"
FORCED_HIGH_RISK_LOW_VALUE = "forced_high_risk_low_value"
FORCED_MEDIUM_RISK_HIGH_VALUE = "forced_medium_risk_high_value"
FORCED_LOW_RISK_HIGH_VALUE = "forced_low_risk_high_value"

FORCED_HIGH_RISK_ARCHETYPES = (
    FORCED_HIGH_RISK_HIGH_VALUE,
    FORCED_HIGH_RISK_MEDIUM_VALUE,
    FORCED_HIGH_RISK_LOW_VALUE,
)

FORCED_ARCHETYPE_VALUE_SEGMENT = {
    FORCED_HIGH_RISK_HIGH_VALUE: "High",
    FORCED_HIGH_RISK_MEDIUM_VALUE: "Medium",
    FORCED_HIGH_RISK_LOW_VALUE: "Low",
    FORCED_MEDIUM_RISK_HIGH_VALUE: "High",
    FORCED_LOW_RISK_HIGH_VALUE: "High",
}

# Order determines index assignment: quotas fill generation indices 0..N-1
# in this order, so index 0 always lands in the first quota group.
FORCED_QUOTA_ORDER = [
    FORCED_HIGH_RISK_HIGH_VALUE,
    FORCED_HIGH_RISK_MEDIUM_VALUE,
    FORCED_HIGH_RISK_LOW_VALUE,
    FORCED_MEDIUM_RISK_HIGH_VALUE,
    FORCED_LOW_RISK_HIGH_VALUE,
]


def _forced_quota_counts(num_customers: int) -> dict[str, int]:
    """Minimum guaranteed counts per forced archetype, scaled to population
    size but never below a floor — keeps the Risk x Value distribution
    guarantee (High x High >= 5, Medium x High >= 10, others exist) true at
    both the 1,200 and 8,000 customer scales CLAUDE.md's demo uses."""

    def scaled(per_8000: int, floor: int) -> int:
        return max(floor, round(num_customers * per_8000 / 8000))

    quotas = {
        FORCED_HIGH_RISK_HIGH_VALUE: scaled(10, floor=5),
        FORCED_HIGH_RISK_MEDIUM_VALUE: scaled(20, floor=2),
        FORCED_HIGH_RISK_LOW_VALUE: scaled(10, floor=2),
        FORCED_MEDIUM_RISK_HIGH_VALUE: scaled(15, floor=10),
        FORCED_LOW_RISK_HIGH_VALUE: scaled(15, floor=2),
    }
    total = sum(quotas.values())
    if total > num_customers:
        raise ValueError(
            f"forced quota total ({total}) exceeds num_customers ({num_customers}); "
            "increase num_customers or lower the quota floors in _forced_quota_counts"
        )
    return quotas


def _forced_archetype_by_index(num_customers: int) -> dict[int, str]:
    quotas = _forced_quota_counts(num_customers)
    assignment: dict[int, str] = {}
    idx = 0
    for archetype in FORCED_QUOTA_ORDER:
        for _ in range(quotas[archetype]):
            assignment[idx] = archetype
            idx += 1
    return assignment

VALUE_SEGMENTS = ["High", "Medium", "Low"]
AGE_BANDS = ["18-24", "25-34", "35-44", "45-54", "55-64", "65+"]
ACQUISITION_CHANNELS = ["Branch", "Online", "Referral", "Partner"]
REGIONS = ["North", "South", "East", "West", "Central"]
CONTACT_CHANNELS = ["Call Center", "Branch", "Chat", "Email"]
CONTACT_REASONS = [
    "Fee Question",
    "Complaint",
    "Service Request",
    "Product Inquiry",
    "Technical Issue",
]
CAMPAIGN_TYPES = [
    "Retention Offer",
    "Cross-Sell Offer",
    "Satisfaction Survey",
    "Product Announcement",
]
CAMPAIGN_CHANNELS = ["Email", "SMS", "Push", "Call"]


def month_end_dates(reference_date: date = REFERENCE_DATE, num_months: int = NUM_MONTHS) -> list[date]:
    """Return num_months month-end dates ending at reference_date, oldest first."""
    dates: list[date] = []
    y, m = reference_date.year, reference_date.month
    for _ in range(num_months):
        dates.append(date(y, m, calendar.monthrange(y, m)[1]))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    dates.reverse()
    return dates


def _weighted_choice(rng: random.Random, options_with_weights: list[tuple[str, float]]) -> str:
    total = sum(w for _, w in options_with_weights)
    r = rng.uniform(0, total)
    upto = 0.0
    for option, w in options_with_weights:
        upto += w
        if r <= upto:
            return option
    return options_with_weights[-1][0]


@dataclass
class CustomerParams:
    customer_id: str
    archetype: str  # internal only, not written to Bronze
    signup_date: date
    tenure_months: int
    age_band: str
    acquisition_channel: str
    home_region: str
    value_segment: str
    simulated_annual_value: float
    base_balance: float
    base_card_spend: float
    base_logins: int
    base_product_count: int
    product_flags: dict[str, bool]
    salary_stop_month: int | None
    product_change_month: int | None
    product_change_type: str | None  # "increase" | "decrease" | None
    churn_label_90d: int


def _make_customer(idx: int, rng: random.Random, forced_archetype: str | None = None) -> CustomerParams:
    customer_id = f"CUST{idx + 1:06d}"
    archetype = _weighted_choice(rng, ARCHETYPES)
    if forced_archetype is not None:
        archetype = forced_archetype

    tenure_months = rng.randint(7, 96)  # at least 7 months so a full 12-month
    # history window doesn't require signup mid-window for most customers;
    # some will still have signed up during the window (new customers), which
    # is intentional and handled by clipping activity before signup_date.
    signup_year = REFERENCE_DATE.year
    signup_month = REFERENCE_DATE.month - tenure_months
    while signup_month <= 0:
        signup_month += 12
        signup_year -= 1
    signup_date = date(signup_year, signup_month, min(28, REFERENCE_DATE.day))

    value_segment = _weighted_choice(
        rng,
        [("High", 0.22), ("Medium", 0.48), ("Low", 0.30)]
        if archetype in ("declining_balance", "strong_retention")
        else [("High", 0.15), ("Medium", 0.50), ("Low", 0.35)],
    )
    if forced_archetype is not None:
        value_segment = FORCED_ARCHETYPE_VALUE_SEGMENT[forced_archetype]
    base_annual_value = {
        "High": rng.uniform(2200, 6000),
        "Medium": rng.uniform(700, 2200),
        "Low": rng.uniform(150, 700),
    }[value_segment]

    base_balance = {
        "High": rng.uniform(25000, 120000),
        "Medium": rng.uniform(4000, 25000),
        "Low": rng.uniform(200, 4000),
    }[value_segment]
    base_card_spend = base_balance * rng.uniform(0.02, 0.06)
    base_logins = rng.randint(4, 30)

    target_product_count = {
        "High": rng.randint(3, 5),
        "Medium": rng.randint(2, 3),
        "Low": rng.randint(1, 2),
    }[value_segment]
    optional_products = ["has_savings", "has_credit_card", "has_loan", "has_investment"]
    rng.shuffle(optional_products)
    n_optional = max(0, min(len(optional_products), target_product_count - 1))
    product_flags = {p: (i < n_optional) for i, p in enumerate(optional_products)}

    salary_stop_month = None
    if archetype == "salary_stopped":
        salary_stop_month = rng.randint(5, 9)

    product_change_month = None
    product_change_type = None
    decline_prob = {
        "declining_balance": 0.20,
        "disengaging": 0.20,
        "service_issues": 0.20,
        "salary_stopped": 0.20,
        "stable_low_risk": 0.05,
        "strong_retention": 0.02,
        FORCED_HIGH_RISK_HIGH_VALUE: 0.0,
        FORCED_HIGH_RISK_MEDIUM_VALUE: 0.0,
        FORCED_HIGH_RISK_LOW_VALUE: 0.0,
        FORCED_MEDIUM_RISK_HIGH_VALUE: 0.0,
        FORCED_LOW_RISK_HIGH_VALUE: 0.0,
    }[archetype]
    increase_prob = {
        "strong_retention": 0.25,
        "stable_low_risk": 0.08,
        "declining_balance": 0.03,
        "disengaging": 0.03,
        "service_issues": 0.03,
        "salary_stopped": 0.03,
        FORCED_HIGH_RISK_HIGH_VALUE: 0.0,
        FORCED_HIGH_RISK_MEDIUM_VALUE: 0.0,
        FORCED_HIGH_RISK_LOW_VALUE: 0.0,
        FORCED_MEDIUM_RISK_HIGH_VALUE: 0.0,
        FORCED_LOW_RISK_HIGH_VALUE: 0.0,
    }[archetype]
    roll = rng.random()
    if roll < decline_prob and n_optional > 0:
        product_change_type = "decrease"
        product_change_month = rng.randint(6, 11)
    elif roll < decline_prob + increase_prob and n_optional < len(optional_products):
        product_change_type = "increase"
        product_change_month = rng.randint(6, 11)

    at_risk_archetypes = (
        "declining_balance",
        "disengaging",
        "service_issues",
        "salary_stopped",
        FORCED_HIGH_RISK_HIGH_VALUE,
        FORCED_HIGH_RISK_MEDIUM_VALUE,
        FORCED_HIGH_RISK_LOW_VALUE,
    )
    if archetype in at_risk_archetypes:
        churn_label_90d = 1 if rng.random() < 0.80 else 0
    elif archetype == "strong_retention":
        churn_label_90d = 1 if rng.random() < 0.01 else 0
    else:
        churn_label_90d = 1 if rng.random() < 0.05 else 0

    return CustomerParams(
        customer_id=customer_id,
        archetype=archetype,
        signup_date=signup_date,
        tenure_months=tenure_months,
        age_band=_weighted_choice(rng, [(b, 1.0) for b in AGE_BANDS]),
        acquisition_channel=_weighted_choice(rng, [(c, 1.0) for c in ACQUISITION_CHANNELS]),
        home_region=_weighted_choice(rng, [(r, 1.0) for r in REGIONS]),
        value_segment=value_segment,
        simulated_annual_value=round(base_annual_value, 2),
        base_balance=round(base_balance, 2),
        base_card_spend=round(base_card_spend, 2),
        base_logins=base_logins,
        base_product_count=1 + n_optional,
        product_flags=product_flags,
        salary_stop_month=salary_stop_month,
        product_change_month=product_change_month,
        product_change_type=product_change_type,
        churn_label_90d=churn_label_90d,
    )


def generate_customers(num_customers: int, seed: int = SEED) -> list[CustomerParams]:
    rng = random.Random(seed)
    forced_by_index = _forced_archetype_by_index(num_customers)
    return [_make_customer(i, rng, forced_by_index.get(i)) for i in range(num_customers)]


def _balance_multipliers(p: CustomerParams, rng: random.Random) -> list[float]:
    if p.archetype in FORCED_HIGH_RISK_ARCHETYPES:
        # Guarantees >=30% balance decline over the trailing 90 days
        # (comfortably above the 30% risk-scoring threshold) regardless of
        # value segment, so every FORCED_HIGH_RISK_* customer scores High.
        vals = [1.0 + rng.uniform(-0.03, 0.03) for _ in range(9)]
        total_decline = rng.uniform(0.38, 0.55)
        last = vals[8]
        for i in range(9, 12):
            frac = (i - 8) / 3
            vals.append(max(0.05, last * (1 - total_decline * frac) + rng.uniform(-0.01, 0.01)))
        return vals
    if p.archetype == "declining_balance":
        vals = [1.0 + rng.uniform(-0.03, 0.03) for _ in range(6)]
        total_decline = rng.uniform(0.35, 0.55)
        last = vals[5]
        for i in range(6, 12):
            frac = (i - 5) / 6
            vals.append(max(0.05, last * (1 - total_decline * frac) + rng.uniform(-0.02, 0.02)))
        return vals
    if p.archetype == "salary_stopped":
        vals = [1.0 + rng.uniform(-0.03, 0.03) for _ in range(12)]
        sm = p.salary_stop_month or 6
        total_decline = rng.uniform(0.15, 0.30)
        base = vals[sm - 1]
        for i in range(sm, 12):
            frac = (i - sm + 1) / max(1, 12 - sm)
            vals[i] = max(0.05, base * (1 - total_decline * frac))
        return vals
    if p.archetype == "strong_retention":
        total_growth = rng.uniform(0.10, 0.25)
        return [1.0 + total_growth * (i / 11) + rng.uniform(-0.02, 0.02) for i in range(12)]
    return [1.0 + rng.uniform(-0.05, 0.05) for _ in range(12)]


def _card_multipliers(p: CustomerParams, rng: random.Random) -> list[float]:
    if p.archetype in FORCED_HIGH_RISK_ARCHETYPES or p.archetype == FORCED_MEDIUM_RISK_HIGH_VALUE:
        # Guarantees >=30% card spend decline over the trailing 90 days.
        vals = [1.0 + rng.uniform(-0.05, 0.05) for _ in range(9)]
        total_decline = rng.uniform(0.38, 0.55)
        last = vals[8]
        for i in range(9, 12):
            frac = (i - 8) / 3
            vals.append(max(0.0, last * (1 - total_decline * frac) + rng.uniform(-0.02, 0.02)))
        return vals
    if p.archetype == "disengaging":
        vals = [1.0 + rng.uniform(-0.05, 0.05) for _ in range(6)]
        total_decline = rng.uniform(0.35, 0.55)
        last = vals[5]
        for i in range(6, 12):
            frac = (i - 5) / 6
            vals.append(max(0.0, last * (1 - total_decline * frac) + rng.uniform(-0.02, 0.02)))
        return vals
    if p.archetype == "strong_retention":
        total_growth = rng.uniform(0.05, 0.20)
        return [1.0 + total_growth * (i / 11) + rng.uniform(-0.03, 0.03) for i in range(12)]
    return [1.0 + rng.uniform(-0.07, 0.07) for _ in range(12)]


def _login_multipliers(p: CustomerParams, rng: random.Random) -> list[float]:
    if p.archetype in FORCED_HIGH_RISK_ARCHETYPES:
        # Guarantees >=50% app login decline over the trailing 90 days.
        vals = [1.0 + rng.uniform(-0.05, 0.05) for _ in range(9)]
        total_decline = rng.uniform(0.60, 0.78)
        last = vals[8]
        for i in range(9, 12):
            frac = (i - 8) / 3
            vals.append(max(0.0, last * (1 - total_decline * frac) + rng.uniform(-0.02, 0.02)))
        return vals
    if p.archetype == "disengaging":
        vals = [1.0 + rng.uniform(-0.05, 0.05) for _ in range(6)]
        total_decline = rng.uniform(0.55, 0.75)
        last = vals[5]
        for i in range(6, 12):
            frac = (i - 5) / 6
            vals.append(max(0.0, last * (1 - total_decline * frac) + rng.uniform(-0.02, 0.02)))
        return vals
    if p.archetype == "strong_retention":
        total_growth = rng.uniform(0.10, 0.30)
        return [1.0 + total_growth * (i / 11) + rng.uniform(-0.03, 0.03) for i in range(12)]
    return [1.0 + rng.uniform(-0.08, 0.08) for _ in range(12)]


def generate_account_transactions(customers: list[CustomerParams], seed: int = SEED) -> list[dict]:
    rng = random.Random(seed + 1)
    months = month_end_dates()
    rows = []
    for p in customers:
        multipliers = _balance_multipliers(p, rng)
        for i, m in enumerate(months):
            if m < p.signup_date:
                continue
            eom_balance = round(p.base_balance * multipliers[i], 2)
            avg_daily_balance = round(eom_balance * rng.uniform(0.92, 1.05), 2)
            salary_active = not (p.salary_stop_month is not None and i >= p.salary_stop_month)
            rows.append(
                {
                    "customer_id": p.customer_id,
                    "activity_month": m,
                    "avg_daily_balance": avg_daily_balance,
                    "eom_balance": eom_balance,
                    "deposit_count": rng.randint(1, 6) + (1 if salary_active else 0),
                    "withdrawal_count": rng.randint(2, 12),
                    "transfer_out_amount": round(max(0.0, rng.uniform(0, eom_balance * 0.15)), 2),
                    "salary_deposit_flag": 1 if salary_active else 0,
                    "total_transaction_amount": round(rng.uniform(500, max(600, eom_balance * 0.5)), 2),
                }
            )
    return rows


def generate_card_usage(customers: list[CustomerParams], seed: int = SEED) -> list[dict]:
    rng = random.Random(seed + 2)
    months = month_end_dates()
    rows = []
    for p in customers:
        multipliers = _card_multipliers(p, rng)
        for i, m in enumerate(months):
            if m < p.signup_date:
                continue
            spend = round(max(0.0, p.base_card_spend * multipliers[i]), 2)
            txn_count = max(0, round(spend / rng.uniform(25, 60)))
            rows.append(
                {
                    "customer_id": p.customer_id,
                    "activity_month": m,
                    "card_spend_amount": spend,
                    "card_txn_count": txn_count,
                    "declined_txn_count": rng.randint(0, 1) if rng.random() < 0.85 else rng.randint(1, 3),
                    "card_active_flag": 1 if spend > 0 else 0,
                }
            )
    return rows


def generate_app_activity(customers: list[CustomerParams], seed: int = SEED) -> list[dict]:
    rng = random.Random(seed + 3)
    months = month_end_dates()
    rows = []
    for p in customers:
        multipliers = _login_multipliers(p, rng)
        for i, m in enumerate(months):
            if m < p.signup_date:
                continue
            logins = max(0, round(p.base_logins * multipliers[i]))
            sessions = max(0, round(logins * rng.uniform(0.9, 1.3)))
            if logins == 0:
                days_since_last_login = rng.randint(35, 90)
            else:
                days_since_last_login = max(0, round(30 / max(logins, 1)) + rng.randint(-1, 2))
            rows.append(
                {
                    "customer_id": p.customer_id,
                    "activity_month": m,
                    "login_count": logins,
                    "session_count": sessions,
                    "avg_session_minutes": round(rng.uniform(1.5, 12.0), 2),
                    "days_since_last_login_eom": days_since_last_login,
                }
            )
    return rows


def generate_contact_history(customers: list[CustomerParams], seed: int = SEED) -> list[dict]:
    rng = random.Random(seed + 4)
    months = month_end_dates()
    recent_months = months[-3:]
    rows = []
    contact_id = 0
    for p in customers:
        if p.archetype == "service_issues":
            n_contacts = rng.randint(3, 6)
            recent_ratio = 0.75
        elif p.archetype in FORCED_HIGH_RISK_ARCHETYPES:
            n_contacts = rng.randint(1, 3)
            recent_ratio = 0.6
        elif p.archetype == FORCED_MEDIUM_RISK_HIGH_VALUE:
            n_contacts = rng.randint(2, 3)
            recent_ratio = 0.7
        elif p.archetype == "stable_low_risk":
            n_contacts = rng.randint(0, 1)
            recent_ratio = 0.2
        else:
            n_contacts = rng.randint(0, 2)
            recent_ratio = 0.3

        n_complaints_forced = (
            2 if p.archetype in ("service_issues", FORCED_MEDIUM_RISK_HIGH_VALUE)
            else 1 if p.archetype in FORCED_HIGH_RISK_ARCHETYPES
            else 0
        )
        # complaint_count_90d (gold) only counts contacts within the trailing
        # 90-day window, so a guaranteed complaint_increase_flag needs its
        # forced complaints to land in that window deterministically rather
        # than via recent_ratio odds.
        n_forced_recent = n_complaints_forced if p.archetype == FORCED_MEDIUM_RISK_HIGH_VALUE else 0
        unresolved_forced = 1 if p.archetype in ("service_issues", *FORCED_HIGH_RISK_ARCHETYPES) else 0

        for c in range(n_contacts):
            use_recent = True if c < n_forced_recent else rng.random() < recent_ratio
            contact_date = rng.choice(recent_months if use_recent else months)
            if contact_date < p.signup_date:
                contact_date = p.signup_date
            is_complaint = 1 if (c < n_complaints_forced or (p.archetype != "stable_low_risk" and rng.random() < 0.15)) else 0
            is_resolved = 0 if (c < unresolved_forced) else (1 if rng.random() < 0.85 else 0)
            contact_id += 1
            rows.append(
                {
                    "contact_id": f"CNT{contact_id:07d}",
                    "customer_id": p.customer_id,
                    "contact_date": contact_date,
                    "channel": rng.choice(CONTACT_CHANNELS),
                    "reason": "Complaint" if is_complaint else rng.choice(
                        [r for r in CONTACT_REASONS if r != "Complaint"]
                    ),
                    "is_complaint": is_complaint,
                    "is_resolved": is_resolved,
                    "satisfaction_score": rng.randint(1, 2) if is_complaint else rng.randint(3, 5),
                }
            )
    return rows


def generate_product_holdings(customers: list[CustomerParams], seed: int = SEED) -> list[dict]:
    rng = random.Random(seed + 5)
    months = month_end_dates()
    rows = []
    for p in customers:
        flags = dict(p.product_flags)
        for i, m in enumerate(months):
            if m < p.signup_date:
                continue
            if p.product_change_month is not None and i == p.product_change_month:
                candidates = list(flags.keys())
                rng.shuffle(candidates)
                if p.product_change_type == "decrease":
                    for key in candidates:
                        if flags[key]:
                            flags[key] = False
                            break
                elif p.product_change_type == "increase":
                    for key in candidates:
                        if not flags[key]:
                            flags[key] = True
                            break
            product_count = 1 + sum(1 for v in flags.values() if v)
            rows.append(
                {
                    "customer_id": p.customer_id,
                    "activity_month": m,
                    "product_count": product_count,
                    "has_checking": 1,
                    "has_savings": int(flags["has_savings"]),
                    "has_credit_card": int(flags["has_credit_card"]),
                    "has_loan": int(flags["has_loan"]),
                    "has_investment": int(flags["has_investment"]),
                }
            )
    return rows


def generate_campaign_history(customers: list[CustomerParams], seed: int = SEED) -> list[dict]:
    rng = random.Random(seed + 6)
    months = month_end_dates()
    rows = []
    campaign_id = 0
    for p in customers:
        n_campaigns = rng.randint(2, 6)
        base_response_rate = 0.28 if p.archetype in ("strong_retention", "stable_low_risk") else 0.15
        base_conversion_rate = 0.10 if p.archetype in ("strong_retention", "stable_low_risk") else 0.04
        for _ in range(n_campaigns):
            campaign_date = rng.choice(months)
            if campaign_date < p.signup_date:
                campaign_date = p.signup_date
            responded = 1 if rng.random() < base_response_rate else 0
            converted = 1 if (responded and rng.random() < base_conversion_rate / max(base_response_rate, 0.01)) else 0
            campaign_id += 1
            rows.append(
                {
                    "campaign_id": f"CMP{campaign_id:07d}",
                    "customer_id": p.customer_id,
                    "campaign_date": campaign_date,
                    "campaign_type": rng.choice(CAMPAIGN_TYPES),
                    "channel": rng.choice(CAMPAIGN_CHANNELS),
                    "responded_flag": responded,
                    "converted_flag": converted,
                }
            )
    return rows


def customers_to_rows(customers: list[CustomerParams]) -> list[dict]:
    """Bronze-facing customer rows. Drops internal generation fields
    (archetype, product_flags, trajectory params) that are not real source
    columns; keeps churn_label_90d as a simulated ground-truth label
    reserved for optional Phase 7 ML validation only."""
    rows = []
    for p in customers:
        rows.append(
            {
                "customer_id": p.customer_id,
                "signup_date": p.signup_date,
                "tenure_months": p.tenure_months,
                "age_band": p.age_band,
                "acquisition_channel": p.acquisition_channel,
                "home_region": p.home_region,
                "customer_value_segment": p.value_segment,
                "simulated_annual_value": p.simulated_annual_value,
                "churn_label_90d": p.churn_label_90d,
            }
        )
    return rows


def generate_all(num_customers: int, seed: int = SEED) -> dict[str, list[dict]]:
    customers = generate_customers(num_customers, seed)
    return {
        "customers": customers_to_rows(customers),
        "account_transactions": generate_account_transactions(customers, seed),
        "card_usage": generate_card_usage(customers, seed),
        "app_activity": generate_app_activity(customers, seed),
        "contact_history": generate_contact_history(customers, seed),
        "product_holdings": generate_product_holdings(customers, seed),
        "campaign_history": generate_campaign_history(customers, seed),
    }
