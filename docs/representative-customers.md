# Representative customer profiles

Selected **programmatically**, not hand-picked, from the actual
`gold.customer_360` / `gold.retention_action_list` tables built from the
fixed-seed generator (`SEED=42`, `NUM_CUSTOMERS=8000`, reference date
2026-06-30). Because the seed is fixed, running
`01_generate_synthetic_data.py` and `02_build_silver_and_gold.py` in your
Databricks workspace with the default widget values reproduces these
exact customer IDs and figures.

These figures were regenerated after the Fix 1 remediation (deterministic
Risk x Value quotas, `notebooks/lib/datagen.py`), which shifted the
generator's internal random-number sequence — the customer IDs below are
current as of that change, not the original Phase 3 selection.

## Flagship demo customer — `CUST000001`

The **fixed** demo customer (generation index 0, always the first
forced-High-risk/High-value slot — see `docs/risk-scoring.md` "Guaranteed
Risk x Value distribution"). Use this one whenever a single, reliable
Customer 360 example is needed — it does not depend on which random
customers happen to be at-risk in a given run.

- Value segment: **High**, current balance $50,702
- `balance_change_90d_pct`: **-45.3%**, `card_spend_change_90d_pct`: **-47.2%**,
  `login_change_90d_pct`: **-83.3%** (32 days since last login)
- One contact on record: a complaint, unresolved, satisfaction 1/5
- Salary deposit **still active** (not stopped)
- Risk score 83/129 (64/100 normalized), risk segment **High**
- Primary driver: Balance decline (90d); secondary: Card spend decline (90d)
- Recommended action: Relationship review (balance outflow) via Call Center;
  human review required
- Story: a high-value customer disengaging on every channel at once
  (balance, card, app) with an unresolved complaint on file — the clearest
  single "why act now, and how" story in the book.

## Other primary-driver examples

Four more customers, found by querying the live tables, covering the
remaining primary drivers plus one "safe" high-value contrast customer —
together with the flagship above, they demonstrate that risk and value are
independent dimensions (CLAUDE.md §10).

### Card + app disengagement — `CUST000116`

- Value segment: **Medium**
- `card_spend_change_90d_pct`: **-35.9%**, `login_change_90d_pct`: **-50.0%**
- Balance roughly flat (-6.4%), no complaints
- Story: simultaneous card and app disengagement with no balance distress
  yet — the customer is quietly drifting from the digital product.

### Service issues — `CUST000252`

- Value segment: **Low**
- `complaint_count_90d`: 3, `unresolved_contacts_total`: 3
- `avg_satisfaction_score_90d`: 2.6 (of 5)
- Story: repeated complaints, all unresolved — a service-recovery case,
  not a product or pricing case.

### Salary deposit stopped — `CUST000101`

- Value segment: **High**
- `salary_deposit_stopped_flag`: 1 (stopped month 8 of 12),
  `balance_change_90d_pct`: **-24.3%**
- Story: a high-value customer whose salary deposit stopped — likely
  switched primary bank or employer, a strong "why now" signal even before
  balance decline alone would cross the risk threshold.

### Strong retention (safe high value) — `CUST000141`

- Value segment: **High**, current balance $139,945
- `balance_change_90d_pct`: **+6.3%**, `complaint_count_90d`: 0
- Story: the necessary contrast case — a high-value customer who is
  **not** at risk, proving the risk score is independent of value rather
  than just re-ranking the highest-value customers.

## How these were found

Query `gold.customer_360` joined to `gold.retention_action_list`, filtering
each category's defining columns (e.g. `card_spend_change_90d_pct <= -0.30
AND login_change_90d_pct <= -0.50 AND complaint_count_90d = 0` for the
disengagement example). The flagship customer needs no query — it is
always `CUST000001` by construction. See
`tests/test_datagen.py::test_cust000001_is_the_fixed_high_risk_high_value_demo_customer`
for the automated check that keeps this guarantee true on every rerun.
