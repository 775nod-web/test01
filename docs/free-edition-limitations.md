# Databricks Free Edition limitations

This document is the single place that consolidates every Free Edition
and build-environment constraint discovered across all phases — CLAUDE.md
§4 anticipated most of these; this records what was actually true for
this build.

## Confirmed constraints (assumed per CLAUDE.md, unchanged)

- Serverless-only compute; one 2X-Small SQL warehouse; fair-use quotas; no
  SLA.
- Maximum of three Databricks Apps per account; Apps auto-stop after up to
  24 hours of inactivity and must be manually restarted
  (`README.md`'s "Restarting the Databricks App" section).
- No SSO, SCIM, private networking, online tables, or production-grade
  enterprise controls.
- No real bank connectivity or real customer data anywhere in this
  project — every table is synthetic (`notebooks/lib/datagen.py`, fixed
  seed).
- Outbound internet access may be restricted; nothing in this project
  depends on external network calls at runtime (the deployed app only
  talks to its own attached SQL warehouse).

## What this specific build session could not verify directly

This entire project was built in a sandboxed coding session with **no
network path to any Databricks workspace** (outbound HTTPS to the target
workspace host returned a 403 organization-policy denial from the
session's egress proxy — confirmed, not retried/worked around). Concretely,
this means:

- **Catalog/schema layout**: whether the target workspace has Unity
  Catalog enabled or only a Hive metastore was never verified in advance.
  Every notebook and the backend (`notebooks/lib/catalog_utils.py`,
  `backend/db.py`) detects this at runtime instead of assuming it, and
  prints/logs which mode it resolved to.
- **Serverless SQL warehouse availability and Databricks Apps quota**:
  not verified — confirm both exist and are running in your workspace
  before Phase 2.
- **Live deployment, restart, and smoke testing**: every "deploy to
  Databricks Apps" and "restart the app" step in `README.md` is written
  from documentation and prior experience, not exercised against a real
  Databricks Apps instance from this session.
- **AI/BI Dashboard (Phase 5)** and **Genie (Phase 7)**: both are
  workspace-UI-only features; neither was configured or tested live. Both
  have documented manual setup steps and a tested SQL fallback instead
  (`docs/dashboard-setup.md`, `docs/genie-setup.md`).

Everything else — the synthetic data pipeline, all SQL, the FastAPI
backend, and the React frontend — **was** verified end-to-end in this
session: a local Spark+Delta session for the SQL/notebooks (catching two
real bugs — an unsupported `CREATE OR REPLACE TABLE ... AS SELECT` and an
under-gated action-recommendation rule — before they reached Databricks),
and a real headless-browser run of the built app for the frontend
(catching a rounding-display bug and a filter-layout bug). See each
phase's commit message for specifics.

## Not implemented in this demo (by design, per CLAUDE.md)

- No real-time/streaming inference — the risk score and retention list
  are batch SQL, rebuilt by rerunning notebooks.
- No fully automated Next Best Action — every recommended action carries
  `human_review_required` and requires a person to approve it before any
  customer contact (`docs/risk-scoring.md`).
- No production-grade model serving — the optional ML baseline
  (`docs/ml-comparison.md`) is a batch comparison, not a serving endpoint.
- No automatic hand-off to external marketing platforms — the
  Retention Actions page and its CSV export are the hand-off point; a
  person or a separate integration takes it from there.

## What is safe to run repeatedly

Every notebook and SQL script in this repo is idempotent — `DROP TABLE IF
EXISTS` + `CREATE TABLE ... AS SELECT` for Silver/Gold tables, and Delta
`mode("overwrite")` for Bronze — so rerunning any phase's notebook after
the first time never requires manual cleanup, and reruns were verified to
produce identical row counts (see `tests/test_retention_logic.py`'s
`test_rerun_is_idempotent` and the equivalent notebook checks).
