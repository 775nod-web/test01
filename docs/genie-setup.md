# Genie setup (Phase 7, optional)

**Optional Tier 2 enhancement.** Genie is a Databricks workspace feature
(natural-language → SQL over curated tables) that can only be configured
and tested inside a real workspace UI — this build has no network path to
any Databricks workspace (see `docs/free-edition-limitations.md`), so I
could not configure or test a live Genie space myself. Instead, this
document gives the exact setup steps to do it in your workspace, and
verifies the four suggested questions' expected answers against the real
SQL fallback (`sql/queries/`) — the same fallback the app itself uses, so
you have a known-correct answer to check Genie's response against.

**The core app never depends on Genie.** Every page works entirely from
`sql/queries/*.sql` regardless of whether Genie is configured.

## Curated tables to expose to Genie

Expose only these three Gold tables — not Bronze or Silver, which are
implementation detail Genie users shouldn't need to reason about:

| Table | Purpose |
|---|---|
| `gold.customer_360` | One row per customer: value, tenure, behavior trends |
| `gold.retention_action_list` | Risk score, segment, driver, recommended action |
| `gold.executive_kpis` | Pre-aggregated top-line KPIs |

## Business glossary (add these as Genie "instructions" / certified terms)

- **Risk segment**: `High` / `Medium` / `Low`, from the transparent
  point-based score in `docs/risk-scoring.md` — not a machine-learning
  prediction.
- **Value segment**: `High` / `Medium` / `Low`, a simulated business value
  tier (`docs/data-dictionary.md`).
- **Primary driver / secondary driver**: the top one or two triggered
  risk signals for a customer, in order of point weight.
- **Estimated value at risk**: a **simulated** proxy
  (`simulated_annual_value × risk_score / 129`), not a real financial
  figure — Genie should never present this as an actual dollar loss.
- **Human review required**: every recommended action needs a person to
  approve it before contact; Genie should not suggest otherwise.

## Column descriptions

Add the descriptions from `docs/data-dictionary.md`'s "Gold: `customer_360`"
and "Gold: `retention_action_list`" sections verbatim as Genie column
comments — they already state units, ranges, and which figures are
simulated.

## Suggested questions and verified expected answers

Computed against an actual 8,000-customer run (`SEED=42`, matching every
other doc in this repo) via the exact SQL the app itself would run, so
these are real, reproducible numbers to check a live Genie response
against — not placeholders.

### 1. "How many high-value customers are high risk?"

```sql
SELECT COUNT(*) FROM gold.retention_action_list
WHERE value_segment = 'High' AND risk_segment = 'High';
```
**Expected answer: 7.**

### 2. "Show customers with both app and card engagement decline."

```sql
SELECT customer_id, card_spend_change_90d_pct, login_change_90d_pct
FROM gold.customer_360
WHERE card_spend_change_90d_pct <= -0.30 AND login_change_90d_pct <= -0.50;
```
**Expected answer: 292 customers** match both conditions (this is exactly
the `disengaging` archetype's intentional pattern — see
`docs/data-quality-report.md`).

### 3. "Group high-risk customers by primary risk driver."

```sql
SELECT primary_driver, COUNT(*) AS n
FROM gold.retention_action_list
WHERE risk_segment = 'High'
GROUP BY primary_driver ORDER BY n DESC;
```
**Expected answer:** `Card spend decline (90d)`: 76, `Salary deposit
stopped`: 8, `Balance decline (90d)`: 5 (sums to the 89 High-risk
customers reported in `docs/risk-scoring.md`).

### 4. "How many high-risk customers still have salary deposits?"

```sql
SELECT COUNT(*) FROM gold.customer_360 c
JOIN gold.retention_action_list r ON r.customer_id = c.customer_id
WHERE r.risk_segment = 'High' AND c.salary_deposit_active = 1;
```
**Expected answer: 81** (of 89 High-risk customers — most High-risk
customers are flagged for reasons *other* than a stopped salary deposit,
which is exactly what you'd expect since `salary_deposit_stopped_flag` is
only one of eight signals).

## Configuring Genie in your workspace

1. **Catalog Explorer** → confirm the three Gold tables above have column
   comments (paste from `docs/data-dictionary.md`).
2. **Genie** → **New Genie space** → select the catalog/schema resolved by
   Phase 2-4 notebooks (check their output for whether it's
   `bank_demo.gold` or `bank_demo_gold` — Unity Catalog vs. Hive metastore,
   auto-detected at runtime, not guessed here).
3. Add the three tables above as the space's data sources.
4. Paste the business glossary terms above into the space's instructions.
5. Test each of the four questions above; compare against the expected
   answers. If a value is off, check that your workspace ran Phases 2-4
   with the same `SEED=42`, `NUM_CUSTOMERS=8000` defaults — different
   scale/seed will change these specific numbers even though the
   generation logic is identical.
6. Note the Genie space URL for the Phase 9 demo handoff — and keep the
   SQL fallback above ready in case a live question doesn't resolve well
   during the demo.

## Fallback if Genie is unavailable or unstable

Every question above has a working SQL query right here, and the same
logic is already exposed via `sql/queries/segment_explorer.sql` and the
`/api/customers` endpoint for ad hoc exploration in the app itself. Do not
depend on Genie for the ten-minute demo — CLAUDE.md is explicit that the
core story must work without it.
