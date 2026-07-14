"""
Unit tests for notebooks/lib/datagen.py.

Run with: pytest tests/test_datagen.py -v
These tests validate the Phase 2 quality gate: deterministic generation,
no duplicate customer IDs, no sensitive-looking identifiers, and the
presence of the intentional churn patterns required by CLAUDE.md.
"""

import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "notebooks" / "lib"))

import datagen  # noqa: E402

N = 2000


def test_deterministic_with_fixed_seed():
    a = datagen.generate_all(N, seed=42)
    b = datagen.generate_all(N, seed=42)
    assert a == b


def test_different_seed_changes_output():
    a = datagen.generate_all(N, seed=42)
    b = datagen.generate_all(N, seed=43)
    assert a["customers"] != b["customers"]


def test_customer_count_and_uniqueness():
    data = datagen.generate_all(N, seed=42)
    customers = data["customers"]
    assert len(customers) == N
    ids = [c["customer_id"] for c in customers]
    assert len(ids) == len(set(ids)), "duplicate customer_id values found"


def test_no_sensitive_looking_identifiers():
    data = datagen.generate_all(N, seed=42)
    card_number_pattern = re.compile(r"\b\d{13,19}\b")
    ssn_pattern = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
    for table_name, rows in data.items():
        for row in rows[:50]:
            for key, value in row.items():
                if isinstance(value, str):
                    assert not card_number_pattern.search(value), (table_name, key, value)
                    assert not ssn_pattern.search(value), (table_name, key, value)
    # customer_id must be the synthetic CUSTxxxxxx format, not a real-looking account number
    for c in data["customers"][:50]:
        assert re.fullmatch(r"CUST\d{6}", c["customer_id"])


def test_referential_integrity():
    data = datagen.generate_all(N, seed=42)
    customer_ids = {c["customer_id"] for c in data["customers"]}
    for table_name in [
        "account_transactions",
        "card_usage",
        "app_activity",
        "contact_history",
        "product_holdings",
        "campaign_history",
    ]:
        referenced = {row["customer_id"] for row in data[table_name]}
        assert referenced <= customer_ids, f"{table_name} references unknown customer_id"


def test_no_nulls_in_required_fields():
    data = datagen.generate_all(N, seed=42)
    for row in data["customers"]:
        for key, value in row.items():
            assert value is not None, f"customers.{key} is null"


def test_value_and_risk_are_not_perfectly_correlated():
    """High-value customers must not all be low risk, and vice versa —
    CLAUDE.md requires risk and value to be separate dimensions."""
    data = datagen.generate_all(N, seed=42)
    customers_by_id = {c["customer_id"]: c for c in data["customers"]}
    rng_customers = datagen.generate_customers(N, seed=42)
    high_value_ids = {c.customer_id for c in rng_customers if c.value_segment == "High"}
    at_risk_archetypes = {"declining_balance", "disengaging", "service_issues", "salary_stopped"}
    high_value_at_risk = [c for c in rng_customers if c.value_segment == "High" and c.archetype in at_risk_archetypes]
    high_value_safe = [c for c in rng_customers if c.value_segment == "High" and c.archetype not in at_risk_archetypes]
    assert len(high_value_at_risk) > 0, "expected some high-value customers to be at risk"
    assert len(high_value_safe) > 0, "expected some high-value customers to be safe"
    assert customers_by_id  # keep linter happy about unused var
    assert high_value_ids


def test_balance_decline_pattern_present():
    """declining_balance archetype: >30% eom_balance drop over the last 90 days (3 months)."""
    customers = datagen.generate_customers(N, seed=42)
    txns = datagen.generate_account_transactions(customers, seed=42)
    by_customer = {}
    for row in txns:
        by_customer.setdefault(row["customer_id"], []).append(row)
    for rows in by_customer.values():
        rows.sort(key=lambda r: r["activity_month"])

    decliners = [c for c in customers if c.archetype == "declining_balance"]
    assert len(decliners) > 0
    found_30pct_decline = 0
    for c in decliners:
        rows = by_customer[c.customer_id]
        if len(rows) < 4:
            continue
        recent = rows[-1]["eom_balance"]
        three_months_ago = rows[-4]["eom_balance"]
        if three_months_ago > 0 and (three_months_ago - recent) / three_months_ago > 0.30:
            found_30pct_decline += 1
    assert found_30pct_decline > 0, "expected at least some declining_balance customers with >30% 90-day drop"


def test_disengaging_shows_card_and_app_decline_together():
    customers = datagen.generate_customers(N, seed=42)
    cards = datagen.generate_card_usage(customers, seed=42)
    apps = datagen.generate_app_activity(customers, seed=42)
    card_by_cust = {}
    for row in cards:
        card_by_cust.setdefault(row["customer_id"], []).append(row)
    app_by_cust = {}
    for row in apps:
        app_by_cust.setdefault(row["customer_id"], []).append(row)
    for d in (card_by_cust, app_by_cust):
        for rows in d.values():
            rows.sort(key=lambda r: r["activity_month"])

    disengaging = [c for c in customers if c.archetype == "disengaging"]
    assert len(disengaging) > 0
    both_declined = 0
    for c in disengaging:
        crows = card_by_cust.get(c.customer_id, [])
        arows = app_by_cust.get(c.customer_id, [])
        if len(crows) < 7 or len(arows) < 7:
            continue
        card_decline = crows[5]["card_spend_amount"] > 0 and (
            (crows[5]["card_spend_amount"] - crows[-1]["card_spend_amount"]) / crows[5]["card_spend_amount"] > 0.30
        )
        app_decline = arows[5]["login_count"] > 0 and (
            (arows[5]["login_count"] - arows[-1]["login_count"]) / arows[5]["login_count"] > 0.50
        )
        if card_decline and app_decline:
            both_declined += 1
    assert both_declined > 0, "expected disengaging customers with both card and app decline"


def test_service_issues_have_complaints_and_unresolved_contact():
    customers = datagen.generate_customers(N, seed=42)
    contacts = datagen.generate_contact_history(customers, seed=42)
    by_customer = {}
    for row in contacts:
        by_customer.setdefault(row["customer_id"], []).append(row)

    service_issue_customers = [c for c in customers if c.archetype == "service_issues"]
    assert len(service_issue_customers) > 0
    matched = 0
    for c in service_issue_customers:
        rows = by_customer.get(c.customer_id, [])
        n_complaints = sum(r["is_complaint"] for r in rows)
        n_unresolved = sum(1 - r["is_resolved"] for r in rows)
        if n_complaints >= 2 and n_unresolved >= 1:
            matched += 1
    assert matched > 0, "expected service_issues customers with >=2 complaints and an unresolved contact"


def test_salary_stopped_pattern_present():
    customers = datagen.generate_customers(N, seed=42)
    txns = datagen.generate_account_transactions(customers, seed=42)
    by_customer = {}
    for row in txns:
        by_customer.setdefault(row["customer_id"], []).append(row)
    for rows in by_customer.values():
        rows.sort(key=lambda r: r["activity_month"])

    stopped = [c for c in customers if c.archetype == "salary_stopped"]
    assert len(stopped) > 0
    matched = 0
    for c in stopped:
        rows = by_customer.get(c.customer_id, [])
        if not rows:
            continue
        if rows[-1]["salary_deposit_flag"] == 0 and any(r["salary_deposit_flag"] == 1 for r in rows[:3]):
            matched += 1
    assert matched > 0, "expected salary_stopped customers whose salary deposits actually stopped"


def test_strong_retention_population_exists():
    customers = datagen.generate_customers(N, seed=42)
    strong = [c for c in customers if c.archetype == "strong_retention"]
    assert len(strong) > 0
    # should skew toward low churn label
    churned = sum(c.churn_label_90d for c in strong)
    assert churned / len(strong) < 0.10


def test_class_balance_within_expected_ranges():
    customers = datagen.generate_customers(N, seed=42)
    counts = Counter(c.archetype for c in customers)
    fractions = {k: v / N for k, v in counts.items()}
    # loose bounds around the configured weights to tolerate sampling noise
    expected = dict(datagen.ARCHETYPES)
    for archetype, expected_frac in expected.items():
        actual_frac = fractions.get(archetype, 0.0)
        assert abs(actual_frac - expected_frac) < 0.06, (archetype, actual_frac, expected_frac)


def _risk_score_and_segment(customers, txns, cards, apps, contacts):
    """Pure-Python mirror of sql/gold/retention_action_list.sql's scoring so
    Fix 1's population guarantees can be verified without a Spark session."""
    from datetime import timedelta

    def by_customer(rows):
        d = {}
        for r in rows:
            d.setdefault(r["customer_id"], []).append(r)
        for v in d.values():
            v.sort(key=lambda r: r["activity_month"])
        return d

    txn_by_cust = by_customer(txns)
    card_by_cust = by_customer(cards)
    app_by_cust = by_customer(apps)
    contact_by_cust: dict = {}
    for r in contacts:
        contact_by_cust.setdefault(r["customer_id"], []).append(r)

    results = {}
    for c in customers:
        cid = c.customer_id
        trows = txn_by_cust.get(cid, [])
        crows = card_by_cust.get(cid, [])
        arows = app_by_cust.get(cid, [])
        conrows = contact_by_cust.get(cid, [])

        balance_decline = len(trows) >= 4 and trows[-4]["eom_balance"] > 0 and (
            (trows[-4]["eom_balance"] - trows[-1]["eom_balance"]) / trows[-4]["eom_balance"] >= 0.30
        )
        card_decline = len(crows) >= 4 and crows[-4]["card_spend_amount"] > 0 and (
            (crows[-4]["card_spend_amount"] - crows[-1]["card_spend_amount"]) / crows[-4]["card_spend_amount"] >= 0.30
        )
        app_decline = len(arows) >= 4 and arows[-4]["login_count"] > 0 and (
            (arows[-4]["login_count"] - arows[-1]["login_count"]) / arows[-4]["login_count"] >= 0.50
        )
        salary_stopped = bool(trows) and trows[-1]["salary_deposit_flag"] == 0 and any(
            r["salary_deposit_flag"] == 1 for r in trows[:3]
        )
        unresolved = sum(1 - r["is_resolved"] for r in conrows)
        complaints_90d = 0
        if trows:
            cutoff = trows[-1]["activity_month"] - timedelta(days=90)
            complaints_90d = sum(1 for r in conrows if r["contact_date"] > cutoff and r["is_complaint"])

        score = (
            (26 if balance_decline else 0)
            + (24 if salary_stopped else 0)
            + (20 if card_decline else 0)
            + (18 if app_decline else 0)
            + (14 if complaints_90d >= 2 else 0)
            + (9 if unresolved >= 1 else 0)
        )
        segment = "High" if score >= 40 else ("Medium" if score >= 15 else "Low")
        results[cid] = {
            "score": score,
            "segment": segment,
            "value_segment": c.value_segment,
            "balance_decline": balance_decline,
            "card_decline": card_decline,
            "app_decline": app_decline,
            "salary_stopped": salary_stopped,
            "unresolved": unresolved,
            "complaints_90d": complaints_90d,
        }
    return results


def _generate_and_score(num_customers):
    data = datagen.generate_all(num_customers, seed=42)
    customers = datagen.generate_customers(num_customers, seed=42)
    return customers, _risk_score_and_segment(
        customers,
        data["account_transactions"],
        data["card_usage"],
        data["app_activity"],
        data["contact_history"],
    )


def test_risk_value_distribution_guarantees_at_1200_and_8000():
    """CLAUDE.md remediation Fix 1: Risk x Value combinations must be
    guaranteed, not left to weighted-random chance, at both demo scales."""
    for num_customers in (1200, 8000):
        _, results = _generate_and_score(num_customers)
        from collections import Counter

        combo_counts = Counter((r["segment"], r["value_segment"]) for r in results.values())
        assert combo_counts[("High", "High")] >= 5, (num_customers, combo_counts)
        assert combo_counts[("Medium", "High")] >= 10, (num_customers, combo_counts)
        assert combo_counts[("High", "Medium")] >= 1, (num_customers, combo_counts)
        assert combo_counts[("High", "Low")] >= 1, (num_customers, combo_counts)
        assert combo_counts[("Low", "High")] >= 1, (num_customers, combo_counts)


def test_cust000001_is_the_fixed_high_risk_high_value_demo_customer():
    """CUST000001 must satisfy every condition the remediation spec requires,
    generated through the normal archetype/trajectory pipeline (not a
    post-hoc rewrite) at both 1,200 and 8,000 customer scales."""
    for num_customers in (1200, 8000):
        customers, results = _generate_and_score(num_customers)
        c0 = customers[0]
        assert c0.customer_id == "CUST000001"
        r = results["CUST000001"]
        assert r["segment"] == "High"
        assert r["value_segment"] == "High"
        assert c0.salary_stop_month is None
        assert not r["salary_stopped"]
        assert r["balance_decline"]
        assert r["card_decline"]
        assert r["app_decline"]
        assert r["unresolved"] >= 1 or r["complaints_90d"] >= 1
        estimated_value_at_risk = round(c0.simulated_annual_value * (r["score"] / 129.0), 2)
        assert estimated_value_at_risk > 0


def test_product_holdings_row_counts_match_active_months():
    data = datagen.generate_all(500, seed=42)
    holdings_by_customer = Counter(r["customer_id"] for r in data["product_holdings"])
    txn_by_customer = Counter(r["customer_id"] for r in data["account_transactions"])
    # every customer active in transactions must have holdings rows for the same months
    for cust_id, count in txn_by_customer.items():
        assert holdings_by_customer[cust_id] == count
