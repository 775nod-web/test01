# Phase 8 — final integration test report

Full-solution test pass across data, backend, frontend, and deployment
readiness, per CLAUDE.md §12 and `docs/prompt-pack/PHASES_05_TO_09.md`
Phase 8. Run from a fresh Python virtual environment and a fresh
`node_modules` install, not reused state from earlier phases.

## Data tests

| Check | Result |
|---|---|
| Generation reruns without manual cleanup | Pass — `notebooks/lib/datagen.py` is deterministic; Bronze/Silver/Gold all rebuild via `DROP TABLE IF EXISTS` + `CREATE TABLE ... AS SELECT` or Delta `overwrite` |
| Row counts | Pass — `docs/data-quality-report.md` (8,000 customers, ~95K monthly rows/domain), reconfirmed at 1,200/8,000-customer scale across Phases 2–7 |
| Uniqueness (no PK duplicates) | Pass — `tests/test_datagen.py::test_customer_count_and_uniqueness`, `tests/test_retention_logic.py::test_row_count_matches_customer_360` |
| Score boundaries | Pass — 6 boundary tests in `tests/test_retention_logic.py` (exact threshold inclusivity, all-signals-max-score, high-value-alone-isn't-high-risk, single-weak-signal-stays-low) |
| Driver/action consistency | Pass — `test_every_medium_high_risk_row_has_a_driver`, `test_low_risk_customers_get_no_action`, `test_recommended_actions_always_flagged_for_human_review` |
| KPI reconciliation | Pass — `test_executive_kpis_reconcile`, `test_executive_overview_matches_executive_kpis_table` |

## Backend tests (`tests/test_backend_api.py`, 16 tests)

| Check | Result |
|---|---|
| Health endpoint | Pass — reports `data_mode` (local/databricks) |
| Successful responses | Pass — all 10 endpoints return 200 with expected shape |
| Invalid query parameters | Pass — `risk_segment=Extreme` rejected with 422 |
| Missing customer | Pass — unknown `customer_id` returns 404, not a 500 or empty 200 |
| SQL failure handling | Verified by code review — `QueryError` wraps all engine exceptions into a safe generic 500 (`backend/main.py::_handle_query_error`); logs details server-side only |
| Response typing | Pass — every endpoint has a Pydantic `response_model`, exercised by the test suite |
| Pagination / row limits | Pass — `test_retention_actions_pagination_no_overlap`; `MAX_LIMIT`/`MAX_EXPORT_ROWS` caps in `backend/services/` |

## Frontend tests

| Check | Result |
|---|---|
| Navigation | Pass — real nav-link clicks (not just direct URL) confirmed for all 4 top-level pages plus Customer 360 drill-down |
| Loading state | Implemented (`LoadingState`, `role="status" aria-live="polite"`); not independently re-screenshotted in Phase 8 since local queries return in <50ms — verified present in Phase 6 code review |
| Empty state | Pass — Segment Explorer with an implausible filter combination shows "No customers match these filters." |
| Error state | Pass — invalid customer ID shows a clear not-found message with a link back, not a crash |
| Filter behavior | Pass — Segment Explorer risk/value/product/decline filters and Retention Actions risk/value filters all verified against real data |
| Customer selection | Pass — table-row click and **keyboard Enter** both navigate to Customer 360 (tested explicitly for accessibility) |
| Mobile and desktop layout | **Bug found and fixed in this phase**: data tables overflowed the mobile viewport, forcing the whole page to scroll horizontally. Fixed with a `.table-scroll` wrapper (`overflow-x: auto`) around every table plus a `overflow-x: hidden` backstop on `body`; reverified `document.body.scrollWidth === window.innerWidth` at a 390px mobile viewport |
| Accessibility basics | Pass — primary nav has `aria-label`, synthetic-data banner has `role="note"`, table rows used as links have `role="button"` + `tabIndex` + `aria-label` + Enter-key handling, verified via real Tab/Enter keyboard interaction in a headless browser, not just code review |

## Deployment tests

| Check | Result |
|---|---|
| Frontend production build | Pass — fresh `npm install` + `npm run build`, 0 TypeScript errors |
| Python dependency installation | Pass — fresh venv, `pip install -r requirements.txt` (production) and `requirements-dev.txt` (adds Spark/DuckDB/ML test tooling) both clean |
| `app.yaml` command | Pass — `python -m backend.main`, verified to actually start the server and serve both `/api/*` and the built SPA (fixed a real bug in Phase 6: the original `python backend/main.py` form doesn't put the repo root on `sys.path`) |
| Databricks Apps deployment | **Not performed** — this build has no network path to any Databricks workspace (see `docs/free-edition-limitations.md`). Steps are documented in `README.md`'s "Deploying to Databricks Apps" section for you to execute. |
| App restart after stopping | **Not performed**, same reason. Documented in `README.md`. |
| SQL warehouse/resource access | **Not performed**, same reason. `backend/db.py`'s Databricks code path (SDK default-auth, runtime UC/Hive detection) is implemented and unit-reasoned but not exercised against a real warehouse from this session. |
| Smoke test from deployed URL | **Not performed**, same reason. Local equivalent: full Playwright click-through of the actual built app (all pages, drill-down, keyboard nav, mobile) — see Phase 6 and this report's frontend section. |

## Secrets and repository hygiene

- `git grep` across all tracked files for token/key-shaped patterns: clean.
- `.gitignore` excludes `backend/static/` (build output), `node_modules/`,
  `.env`, local Spark/Delta scratch directories.
- `backend/local_fixtures/*.parquet` (committed, ~670KB) contains only
  synthetic data from `notebooks/lib/datagen.py` — no real customer data
  exists anywhere in this repository.

## Documentation completeness

All required documents exist and are current as of this phase:
`README.md`, `docs/architecture.md`, `docs/data-dictionary.md`,
`docs/free-edition-limitations.md` (consolidated in this phase),
`docs/poc-success-criteria.md` (finalized in this phase),
`docs/risk-scoring.md`, `docs/dashboard-setup.md`, `docs/ml-comparison.md`,
`docs/genie-setup.md`, `docs/representative-customers.md`,
`docs/data-quality-report.md`. `docs/demo-script.md` remains a
placeholder by design — it is explicitly Phase 9's deliverable (timed
rehearsal), not Phase 8's.

## Overall result

**63/63 automated tests passed.** Core demo (Phases 1–6) works completely
without any optional feature (Phase 7). One real mobile-layout bug was
found and fixed during this phase's testing. The only checks not
performed are the ones structurally impossible from this sandboxed
session (live Databricks Apps deployment, restart, and smoke test) —
each has documented manual steps in `README.md` instead of being silently
skipped.
