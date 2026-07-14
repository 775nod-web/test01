# Representative customer profiles (Phase 3)

Selected **programmatically**, not hand-picked, by querying the actual
`gold.customer_360` table built from the fixed-seed generator
(`SEED=42`, `NUM_CUSTOMERS=8000`, reference date 2026-06-30). Because the
seed is fixed, running `01_generate_synthetic_data.py` and
`02_build_silver_and_gold.py` in your Databricks workspace with the
default widget values reproduces these exact customer IDs and figures.

These five cover every primary risk driver plus one "safe" high-value
contrast customer, to demonstrate that risk and value are independent
dimensions (CLAUDE.md §10).

## 1. High value, balance decline — `CUST000090`

- Value segment: **High**, current balance $22,435
- `balance_change_90d_pct`: **-40.4%**
- Card spend and app logins roughly flat, no complaints
- Story: a high-value customer quietly moving money elsewhere — the
  single clearest "why act now" balance-outflow case for the demo.

## 2. Card + app disengagement — `CUST001108`

- Value segment: **Medium**
- `card_spend_change_90d_pct`: **-33.4%**, `login_change_90d_pct`: **-66.7%**
- `days_since_last_login`: 31
- Story: simultaneous card and app disengagement — the customer is
  quietly drifting away from the digital product, not showing balance
  distress yet.

## 3. Service issues — `CUST000796`

- Value segment: **Low**
- `complaint_count_90d`: 4, `unresolved_contacts_total`: 2
- `avg_satisfaction_score_90d`: 1.75 (of 5)
- Story: repeated complaints with an unresolved case — a service-recovery
  case, not a product or pricing case.

## 4. Salary deposit stopped — `CUST006272`

- Value segment: **High**
- `salary_deposit_stopped_flag`: 1, `balance_change_90d_pct`: **-29.75%**
- Story: a high-value customer whose salary deposit stopped mid-year —
  likely switched primary bank or employer, a strong "why now" signal.

## 5. Strong retention (safe high value) — `CUST007938`

- Value segment: **High**, current balance $75,068
- `balance_change_90d_pct`: **+9.3%**, `complaint_count_90d`: 0
- Story: the necessary contrast case — a high-value customer who is
  **not** at risk, proving the risk score is independent of value rather
  than just re-ranking the highest-value customers.

## How these were found

See the "Representative customer profiles" cell in
`notebooks/02_build_silver_and_gold.py`, which runs the same five
queries against the live `gold.customer_360` table. The underlying
figures above were captured from a local Spark+Delta run of the exact
`sql/silver/*.sql` and `sql/gold/customer_360.sql` files in this repo
against the Phase 2 generator's output, before this notebook was
committed.
