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
| High | >= 40 | 1.1% (89 customers) |
| Medium | 15–39 | 31.6% (2,529 customers) |
| Low | < 15 | 67.3% (5,382 customers) |

A single weak, isolated signal (e.g. one unresolved contact = 9 points)
stays **Low** risk and gets **no recommended action** — only combinations
of signals reaching 15+ points warrant a retention campaign action. This
was fixed during validation: an earlier version assigned an action to any
customer with a nonzero primary driver regardless of overall segment,
which produced Low-risk customers with a recommended action but no
human-review flag. See the Phase 4 commit for details.

**Risk and value are independent by design** — the 8,000-customer run
shows High risk spread across all three value segments (7 High-value, 33
Low-value, 49 Medium-value), not concentrated in high-value customers.

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

## Action priority (combining risk and value)

`action_priority_score = risk_score + value_bonus`, where `value_bonus` is
+15 for High value, +5 for Medium, +0 for Low. `action_priority_rank` is a
dense rank over this score, descending — this is what the Retention
Actions page (Phase 6) sorts by, so equally-risky customers are prioritized
by value without value alone determining risk.

## Human review

`human_review_required = 1` whenever `risk_segment` is Medium or High
(i.e., whenever an action is recommended). This table is decision support:
no action in this pipeline sends a message, opens a case, or changes an
account — a person reviews and executes.
