# Digital Bank Customer Retention Demo

Executive demo for a digital-native bank, built for **Databricks Free Edition**.
It turns fragmented customer data (app activity, accounts, cards, loans,
contacts, products, campaigns) into a unified **Customer 360** view, a
transparent churn-risk score, and a human-reviewed retention action list —
so a marketing/CRM leader can answer: *"Where should we focus limited
retention budget, and on whom?"*

The primary use case is **customer retention**. Cross-sell is shown only as
a future reuse path for the same Customer 360 data, not a second demo.

See `CLAUDE.md` at the repo root for the full project contract (business
storyline, constraints, UI principles, and quality gates that govern every
phase of this build).

## Purpose

1. Unify fragmented customer data into one Customer 360 record per customer.
2. Identify customers who are both high-value and high churn-risk.
3. Explain *why* each customer is at risk with transparent, rule-based drivers.
4. Recommend a human-reviewed retention action and channel.
5. Show how the same Customer 360 table can later support cross-sell.

## Architecture

```text
React + TypeScript frontend (built to static assets)
          |
          | same-origin HTTP API
          v
Python FastAPI backend
          |
          | Databricks SQL / Databricks SDK
          v
Gold Delta tables in Unity Catalog (bank_demo.gold.*)
```

- Frontend: TypeScript + React, built with Vite into static assets.
- Backend: Python FastAPI, serves the built frontend and exposes typed
  `/api/*` endpoints backed by Databricks SQL queries against Gold tables.
- Data: synthetic-only, generated inside Databricks notebooks
  (`notebooks/`), landed as Bronze → Silver → Gold Delta tables under a
  `bank_demo.bronze` / `bank_demo.silver` / `bank_demo.gold` catalog/schema
  pattern.
- No Streamlit. No Node.js/Express backend — Node is used only to build the
  React bundle.
- Deployment target: **Databricks Apps**. A local server is a development
  convenience only, never the final deliverable.

```text
project-root/
├── app.yaml                 # Databricks Apps runtime config
├── requirements.txt         # Python backend dependencies
├── package.json             # root build wrapper (builds frontend only)
├── CLAUDE.md                # persistent project contract
├── README.md                # this file
├── backend/                 # FastAPI app (main.py, config.py, db.py, schemas.py, services/)
├── frontend/                # React + TypeScript app (Vite)
├── notebooks/                # Databricks notebooks: data generation, Silver/Gold builds
├── sql/                      # Dashboard + app SQL queries
├── tests/                    # Backend/frontend/data tests
├── docs/                     # architecture, demo script, data dictionary, limitations, PoC criteria
└── legacy/                   # archived, unrelated prior-session content (not part of this project)
```

## Prerequisites

- A Databricks workspace with **Free Edition** enabled.
- Ability to create a Unity Catalog catalog/schema (or use an existing one
  you have write access to) for `bronze` / `silver` / `gold` schemas.
- A serverless SQL warehouse (2X-Small) for querying Gold tables.
- Databricks Apps enabled on the workspace (checked at Phase 6; if
  unavailable, the app source and deployment steps are still delivered —
  see "Databricks Apps availability" below).
- Node.js ≥ 20 and Python ≥ 3.11 locally (for building/testing before
  deployment); this repo was built and tested with Node 22.22 / Python 3.11.

## Free Edition constraints assumed throughout

- Serverless-only compute; one 2X-Small SQL warehouse; fair-use quotas; no SLA.
- Maximum of three Databricks Apps per account; Apps may auto-stop after up
  to 24 hours and must be restartable.
- No SSO/SCIM/private networking/online tables/production-grade controls.
- No real bank connectivity or real customer data — everything is synthetic,
  generated inside Databricks with a fixed random seed.
- Outbound internet access from notebooks/apps may be restricted; nothing in
  this project depends on external network calls at runtime.
- This project is a demo, not a production system. Free Edition is not
  presented as production-ready anywhere in the app or docs.

## Databricks Apps availability

**Status: unknown / to be confirmed by you.** This repository was built in a
sandboxed coding session with **no network path to the target Databricks
workspace** (outbound HTTPS to the workspace host was blocked by session
egress policy). As a result:

- Catalog/schema names, serverless SQL warehouse status, and Databricks Apps
  quota **could not be verified from this session** and are not guessed.
- All notebooks, SQL, and the FastAPI/React app are written to be run **by
  you**, inside the actual Databricks workspace (via the workspace UI, a
  notebook, or your own terminal with `databricks` CLI access).
- Before Phase 2, confirm in your workspace: the catalog you'll use (default
  assumed: `bank_demo`), that a serverless SQL warehouse exists and is
  running, and that Databricks Apps is enabled for your account (Account
  Console → Previews, or Compute → Apps in the workspace).
- If Databricks Apps turns out to be unavailable, Phase 6 will still deliver
  complete backend/frontend source, a working local dev flow, and the exact
  deployment steps to run once Apps is enabled — it will not be replaced by
  Streamlit or a local-only substitute.

## Synthetic data generation (Phase 2)

`notebooks/lib/datagen.py` is a pure-Python, deterministic generator (fixed
seed, stdlib only) that produces all seven source domains with intentional,
explainable churn/retention patterns. It has no Spark dependency, so it is
unit-tested directly:

```bash
pip install -r requirements.txt
pytest tests/test_datagen.py -v          # 14 tests: determinism, uniqueness,
                                          # referential integrity, patterns
python tests/generate_quality_report.py  # regenerates docs/data-quality-report.md
```

To materialize the data as Bronze Delta tables, run
`notebooks/01_generate_synthetic_data.py` inside your Databricks workspace
(import the repo as a Databricks Repo so `notebooks/lib` is importable
alongside it). The notebook:

- detects at runtime whether Unity Catalog is enabled and falls back to a
  Hive metastore database automatically — this was **not** guessed, since
  this build had no network path to verify it in advance;
- is idempotent (`mode("overwrite")` on every table), so it can be rerun
  without manual cleanup;
- runs its own row-count, null, and referential-integrity checks after
  writing, in addition to `docs/data-quality-report.md`.

See `docs/data-dictionary.md` for full column definitions and
`docs/data-quality-report.md` for measured row counts, ranges, class
balance, and pattern verification from an actual 8,000-customer run.

## Silver layer and Customer 360 (Phase 3)

`sql/silver/*.sql` clean each Bronze domain (type casts, de-dup,
categorical standardization, customer_id validation, referential
integrity). `sql/gold/customer_360.sql` builds one row per customer with
value, account, card, app, service, and campaign behavior — see
`docs/data-dictionary.md` for every column.

Run `notebooks/02_build_silver_and_gold.py` in Databricks after Phase 2's
notebook, in the same catalog/schema. Both notebooks share
`notebooks/lib/catalog_utils.py` to detect Unity Catalog vs. Hive
metastore consistently. All tables are rebuilt with `DROP TABLE IF
EXISTS` + `CREATE TABLE ... AS SELECT` (rerunnable, and the pattern that
actually works — `CREATE OR REPLACE TABLE ... AS SELECT` failed against a
local Delta catalog during validation and was replaced for portability).

The notebook's own reconciliation cell asserts: one `customer_360` row
per valid Silver customer, no duplicate `customer_id`, no negative
balances, no null `value_segment`. All of this — plus the SQL and the
Spark write/rerun path — was validated end-to-end against a local
Spark+Delta session built from the actual Phase 2 generator output before
being committed; see `docs/representative-customers.md` for five
real, reproducible customer stories (one per risk driver, plus a
high-value "safe" contrast case) pulled from that same run.

## Risk scoring and retention actions (Phase 4)

`sql/gold/retention_action_list.sql` computes a transparent, configurable
point score (8 signals, max 129 points) into `High`/`Medium`/`Low` risk
segments with an explainable primary/secondary driver, a recommended
action + channel (Medium/High risk only), a mandatory
`human_review_required` flag, and a labeled **simulated**
`estimated_value_at_risk`. `sql/gold/executive_kpis.sql` aggregates this
into one summary row. Full rule and threshold documentation:
`docs/risk-scoring.md`.

This is not a predictive model — see `docs/prompt-pack/PHASES_05_TO_09.md`
Phase 7 for the optional ML comparison, which never becomes a dependency
of the core demo.

Run `notebooks/03_build_risk_and_retention.py` in Databricks after Phase 3.
Boundary conditions (every threshold, plus "no signals," "all signals,"
and "high value alone isn't high risk") are covered in
`tests/test_retention_logic.py`, which also rebuilds the full pipeline at
smaller scale and checks reconciliation, human-review gating, and rerun
idempotency. This suite needs Spark and is **not** part of the FastAPI
backend's dependencies, so install it separately:

```bash
pip install pyspark==3.5.3 delta-spark==3.2.1
pytest tests/test_retention_logic.py -v
```

Without pyspark installed, this file is skipped automatically (`pytest
tests/` still runs the Phase 2 generator tests).

## Restarting the Databricks App (once deployed)

1. Open the workspace → **Compute → Apps**.
2. Select the app (e.g. `bank-retention-demo`).
3. If status shows **Stopped**, click **Start**. Apps on Free Edition may
   auto-stop after up to 24 hours of inactivity — this is expected, not a
   failure.
4. Wait for status **Running**, then open the app URL.
5. Verify the SQL warehouse resource attached to the app is also running
   (Compute → SQL Warehouses); start it if stopped.
6. Hit `/api/health` on the app URL to confirm the backend can reach Gold
   tables before presenting.

## Phase checklist

| Phase | Scope | Status |
|---|---|---|
| 1 | Repository and environment scaffolding | Done |
| 2 | Synthetic banking data (Bronze) | Done — run `notebooks/01_generate_synthetic_data.py` in Databricks to materialize tables |
| 3 | Silver layer and Customer 360 (Gold) | Done — run `notebooks/02_build_silver_and_gold.py` after Phase 2 |
| 4 | Rule-based risk score and retention actions | Done — run `notebooks/03_build_risk_and_retention.py` after Phase 3 |
| 5 | Executive dashboard and SQL assets | Not started |
| 6 | React + FastAPI app on Databricks Apps | Not started |
| 7 | Optional ML / MLflow / Genie (never a dependency) | Not started |
| 8 | Integration testing, deployment, documentation | Not started |
| 9 | Ten-minute demo rehearsal and handoff | Not started |

## Planned application usage (once Phase 6 is deployed)

1. Open the deployed Databricks Apps URL.
2. Start at **Executive Overview** — where should retention budget focus?
3. Open **Segment Explorer** — which behavior pattern should the campaign address?
4. Select a customer in **Customer 360** — why is this customer at risk, and how should we respond?
5. Open **Retention Actions** — who should receive which action first?
6. Finish at **PoC & Future Expansion** — what must be validated with real bank data, and how does this extend to cross-sell?

## Documentation

- `docs/architecture.md` — system architecture (added in later phases).
- `docs/demo-script.md` — timed ten-minute script (Phase 9).
- `docs/data-dictionary.md` — column-level data dictionary (Phase 2–4).
- `docs/free-edition-limitations.md` — what Free Edition cannot do here.
- `docs/poc-success-criteria.md` — what a production PoC would validate.

## Troubleshooting (placeholder — expanded in later phases)

- **App won't start**: check Compute → Apps logs; verify `app.yaml`
  command and that `requirements.txt` installed cleanly.
- **No data in UI**: verify the SQL warehouse is running and the app's
  attached warehouse resource matches the one hosting `bank_demo.gold.*`.
- **Notebook errors on rerun**: all Phase 2–4 notebooks are designed to be
  idempotent (`CREATE OR REPLACE TABLE`); rerun from the top rather than
  patching state manually.

## Limitations (summary — full detail in `docs/free-edition-limitations.md`)

No real bank connectivity, no production-grade identity/security controls,
no mandatory real-time inference, no fully automated retention decisions
(human review is required), and no guarantee of uptime/SLA on Free Edition.
