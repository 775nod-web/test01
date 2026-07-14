# Risk scoring and retention action rules

This is a **transparent, configurable prioritization score** — it is
explicitly not a predictive machine-learning model (see
`docs/prompt-pack/PHASES_05_TO_09.md` Phase 7 for the optional ML
comparison). It exists to rank customers for retention outreach, not to
make an automated financial decision. Every recommended action requires
human review before any customer contact (CLAUDE.md §11).

Built by `sql/gold/retention_action_list.sql`, reading `gold.customer_360`
(Phase 3). Validated against a local Spark+Delta session with the real
8,000-customer generator output plus hand-crafted boundary rows — see
`tests/test_retention_logic.py`.

## Scoring rule

Eight independent signals, each contributing points if triggered. Point
values are deliberately distinct so ranking by points alone resolves
primary vs. secondary driver without a separate tie-break rule.

| Signal | Threshold | Points | Source column |
|---|---|---|---|
| Balance decline | `balance_change_90d_pct <= -30%` | 26 | `customer_360.balance_change_90d_pct` |
| Salary deposit stopped | `salary_deposit_stopped_flag = 1` | 24 | `customer_360.salary_deposit_stopped_flag` |
| Card spend decline | `card_spend_change_90d_pct <= -30%` | 20 | `customer_360.card_spend_change_90d_pct` |
| App usage decline | `login_change_90d_pct <= -50%` | 18 | `customer_360.login_change_90d_pct` |
| Rising complaints | `complaint_count_90d >= 2` | 14 | `customer_360.complaint_count_90d` |
| Long app inactivity | `days_since_last_login >= 30` | 10 | `customer_360.days_since_last_login` |
| Unresolved contact | `unresolved_contacts_total >= 1` | 9 | `customer_360.unresolved_contacts_total` |
| Product holding decreased | `product_count_change_90d < 0` | 8 | `customer_360.product_count_change_90d` |

**Maximum possible score: 129.** All thresholds are inclusive (`<=`/`>=`)
— e.g. a customer at exactly -30.00% balance change triggers the signal.

## Risk segments

Thresholds were chosen by inspecting the actual score distribution from an
8,000-customer run (via `tests/test_retention_logic.py` / local
validation), not picked arbitrarily:

| Segment | Score range | Observed share (8,000-customer run) |
|---|---|---|
| High | >= 40 | 1.2% (94 customers) |
| Medium | 15–39 | 31.9% (2,548 customers) |
| Low | < 15 | 67.0% (5,358 customers) |

A single weak, isolated signal (e.g. one unresolved contact = 9 points)
stays **Low** risk and gets **no recommended action** — only combinations
of signals reaching 15+ points warrant a retention campaign action. This
was fixed during validation: an earlier version assigned an action to any
customer with a nonzero primary driver regardless of overall segment,
which produced Low-risk customers with a recommended action but no
human-review flag. See the Phase 4 commit for details.

**Risk and value are independent by design** — the 8,000-customer run
shows High risk spread across all three value segments (21 High-value, 23
Low-value, 50 Medium-value), not concentrated in high-value customers.

### Guaranteed Risk x Value distribution (Fix 1)

Left to pure weighted-random chance, the High-risk x High-value
intersection — the population this demo's storyline is built around —
could shrink to zero on an unlucky seed or a small customer count. Since
the storyline requires it to always be demonstrable, `notebooks/lib/datagen.py`
reserves a small, deterministic block of "forced archetype" customers
(`_forced_quota_counts`) at the front of every generated population, sized
as a fraction of population but never below a floor:

| Combination | Guarantee | 1,200-customer run | 8,000-customer run |
|---|---|---|---|
| High risk x High value | >= 5 | 9 | 21 |
| Medium risk x High value | >= 10 | 71 | 447 |
| High risk x Medium value | exists | 9 | 50 |
| High risk x Low value | exists | 6 | 23 |
| Low risk x High value | exists | 129 | 875 |

`CUST000001` (generation index 0) is always the first forced High-risk /
High-value customer — the fixed demo customer referenced throughout the
app, `docs/demo-script.md`, and `docs/representative-customers.md`. It is
generated through the same archetype/trajectory pipeline as every other
customer (not rewritten after the fact): balance, card spend, and app
login all decline over the trailing 90 days (>=30%, >=30%, >=50%
respectively), salary deposits keep arriving, and one contact exists and
is unresolved. See `tests/test_datagen.py::test_cust000001_is_the_fixed_high_risk_high_value_demo_customer`.

## Normalized display score

The UI shows risk on a familiar 0-100 scale, but the internal 129-point
scale above (and its High/Medium/Low thresholds) remains the actual source
of truth everywhere — the 100-point figure is a display-only projection
computed once, in SQL, and passed through unchanged:

```
risk_score_normalized_100 = ROUND(risk_score / 129 * 100)
```

`triggered_signal_count` (0-8) is how many of the eight signals above
fired for that customer, shown alongside as "N / 8". Both columns are
computed in `sql/gold/retention_action_list.sql` and surfaced through
`customer_360_summary.sql` → `CustomerDetailResponse` → Customer 360's
risk score card (e.g. "Risk score: 72 / 100", "Risk segment: High",
"Signals detected: 5 / 8").

## Driver selection

`primary_driver` = the highest-point triggered signal; `secondary_driver`
= the second-highest, or `'None'` if only one signal triggered. A customer
with no triggered signals gets `primary_driver = 'No material risk
driver'` and is always Low risk.

## Retention action mapping

Actions and channels are assigned **only** when `risk_segment` is Medium
or High — Low-risk customers always get `'No immediate action'` and
`human_review_required = 0`.

| Primary driver | Recommended action | Channel |
|---|---|---|
| Unresolved service contact | Priority service recovery | Call Center |
| Rising complaints | Fee/service-plan review | Call Center |
| Card spend decline (90d) | Targeted card benefit message | Push/App |
| App engagement decline (90d) | Personalized in-app engagement message | Push/App |
| Long app inactivity | Personalized in-app engagement message | Push/App |
| Balance decline (90d) | Relationship review (balance outflow) | Call Center |
| Salary deposit stopped | Relationship review (income change) | Call Center |
| Product holding decreased | Product/portfolio review | Email |
| (none / Low risk) | No immediate action | None |

## Estimated value at risk

`estimated_value_at_risk = simulated_annual_value × (risk_score / 129)` —
a **labeled simulated proxy**, not an actuarial or financial estimate. It
scales the customer's simulated annual value by the fraction of maximum
risk points triggered, so a customer with more/stronger signals shows a
higher figure, but the number itself carries no real-world guarantee.

## Priority ranking formula (combining risk, value, value-at-risk, actionability)

The Retention Actions page ranks customers by a single `action_priority_rank`,
so "who gets contacted first" needs one defensible answer, not four
separate sort options. The UI intentionally does **not** show the formula
below — only this fixed sentence:

> Priority is calculated by combining churn risk, customer value,
> estimated value at risk, and actionability.
> (優先順位は、解約リスク、顧客価値、推定価値リスク、介入可能性を組み合わせて算出しています。)

### The two candidates compared

An earlier version simply added `risk_score + value_bonus` (+15 High,
+5 Medium, +0 Low), which let a maxed-out High-risk/Low-value customer
outrank a Medium-risk/High-value one — not what "prioritize high-value,
at-risk customers" should mean, and it used `RANK()`, which ties (two
customers could both show "#1"). Two replacement designs were compared on
the real 1,200-customer generated population (`risk_segment IN ('High',
'Medium')`, n=416) before choosing:

**Multiplicative**: `risk_norm x value_weight x (1 + value_at_risk_norm) x actionability_weight`

**Additive (normalized weighted sum)**: `0.40 x risk_norm + 0.30 x value_weight + 0.20 x value_at_risk_norm + 0.10 x actionability_weight`

Where `risk_norm = risk_score / 129`, `value_weight` is High=1.0/Medium=0.6/Low=0.3,
`value_at_risk_norm = estimated_value_at_risk / max(estimated_value_at_risk)`
over the whole population, and `actionability_weight` is 1.0 if salary
deposits are still active (a live primary relationship — outreach is more
likely to land) or 0.7 if they've stopped.

| Criterion | Multiplicative | Additive (normalized) | Winner |
|---|---|---|---|
| Explainable to a CMO | Interaction of 4 multiplied terms; harder to state as a sentence | "40% risk + 30% value + 20% value-at-risk + 10% actionability" — a familiar weighted-scorecard pattern | **Additive** |
| High risk x High value generally top-ranked | 10 of top 20 | 10 of top 20 | Tie |
| Medium x High reasonably exceeds High x Low | 51/72 Medium x High customers beat every High x Low customer | 72/72 do (a stronger, business-aligned result: value is a real priority axis here, not just a tiebreaker) | **Additive** |
| No single factor dominates | Highest single-factor correlation to final score: 0.90 (value-at-risk) | Highest single-factor correlation to final score: 0.91 (value-at-risk) | Tie (both acceptable, well under 1.0) |
| Deterministic (same input -> same output) | Yes | Yes | Tie |

**Adopted: the additive, normalized weighted sum.** It reads as a single
sentence a CMO can repeat back, and it more cleanly reflects this demo's
explicit storyline — prioritizing high-value, at-risk customers, not risk
alone — without any one factor deciding the outcome by itself.

```
action_priority_score = 0.40 * (risk_score / 129)
                       + 0.30 * value_weight        (High=1.0, Medium=0.6, Low=0.3)
                       + 0.20 * value_at_risk_norm   (estimated_value_at_risk / population max)
                       + 0.10 * actionability_weight (1.0 active salary deposits, else 0.7)
```

`action_priority_rank = ROW_NUMBER() OVER (ORDER BY action_priority_score DESC, customer_id ASC)`
— unique and sequential (1, 2, 3, ...), never tied, with `customer_id` as a
deterministic final tiebreaker. `priority_tier` splits the same ordering
into three even bands via `NTILE(3)`: **A** (top third, most urgent) down
to **C** (bottom third). See `tests/test_retention_logic.py::test_action_priority_rank_is_unique_and_tiers_are_valid`
and `::test_high_risk_high_value_generally_ranks_above_high_risk_low_value`.

## Human review

`human_review_required = 1` whenever `risk_segment` is Medium or High
(i.e., whenever an action is recommended). This table is decision support:
no action in this pipeline sends a message, opens a case, or changes an
account — a person reviews and executes.
