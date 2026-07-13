# Phases 05 to 09 — Analytics, Databricks App, validation, and handoff

> Execute these phases in order. Phase 7 is optional and must not become a dependency of the core demo. Stop at each quality gate, test the outputs, update README.md, and report unresolved issues before continuing.

# Phase 5 — executive dashboard and SQL assets

Read `CLAUDE.md` and validate all mandatory Gold tables.

Create the query and visualization assets needed for the ten-minute storyline.

## Executive Overview

Include:

- total customers;
- high-risk customers;
- high-risk and high-value customers;
- simulated estimated value at risk;
- broad audience versus prioritized audience;
- risk distribution;
- value-versus-risk matrix;
- top drivers.

## Segment Explorer

Support filtering or parameterized analysis for:

- risk segment;
- value segment;
- product holdings;
- balance decline;
- card-spend decline;
- app decline;
- contact and complaint activity.

## Customer 360 query

Create a reliable query for a selected customer with trends, drivers, value, and recommendation.

## Retention Actions query

Create a prioritized campaign list with action, channel, driver, risk, and value.

## Cross-sell future-view specification

Do not build a second major use case. Create one small visual or documented query showing how product gaps and behavior could later support cross-sell.

## Output options

If AI/BI dashboard creation is available and stable, create it. In all cases, save the underlying SQL queries so the Databricks App can use them.

Genie is optional. Do not make the phase depend on Genie.

## Quality gate

- all KPI totals match Gold tables;
- filters return expected results;
- no unsupported outcome claim is shown;
- charts have concise executive labels;
- the core story can be completed without Genie;
- SQL is documented for app integration.

Report the dashboard or query assets created and stop after Phase 5.

---

# Phase 6 — React and Python application on Databricks Apps

Read `CLAUDE.md` and validate the data and SQL assets.

Build the final application for Databricks Apps.

## Non-negotiable architecture

- Frontend: TypeScript + React.
- Backend: Python FastAPI or an equivalent Python framework.
- Do not use Streamlit.
- Do not use Node.js or Express for backend APIs.
- Node tooling may only build the React frontend.
- Serve the built React static assets from the Python backend.
- Query Databricks Gold tables through the Python backend.
- Use environment variables or attached Databricks resources; do not hardcode tokens or secrets.
- Configure runtime with `app.yaml`.
- Bind to `0.0.0.0` and `DATABRICKS_APP_PORT`.
- Deploy the final app to Databricks Apps. Do not stop at local execution.

## Required pages

1. Executive Overview.
2. Segment Explorer.
3. Customer 360.
4. Retention Actions.
5. PoC and Future Expansion.

## API expectations

Create typed endpoints similar to:

- `/api/health`
- `/api/kpis`
- `/api/risk-distribution`
- `/api/segments`
- `/api/customers`
- `/api/customers/{customer_id}`
- `/api/retention-actions`
- `/api/poc-summary`

Use server-side validation, safe query parameters, sensible limits, and clear error responses.

## UI requirements

Use the palette and design principles in `CLAUDE.md`.

Include:

- responsive layout;
- loading states;
- empty states;
- error states;
- explanatory tooltips;
- visible “Synthetic demo data” indicator;
- visible “Human review required” status for recommendations;
- accessible controls;
- no unnecessary animations.

The UI must make business questions prominent. Avoid technical labels such as table names on executive pages.

## App usage documentation

Update the project README with exact instructions for:

- deploying or redeploying the app;
- starting or restarting it;
- attaching the SQL warehouse or required resources;
- opening the application;
- navigating the five pages;
- executing the ten-minute demo;
- troubleshooting common failures.

## When Databricks Apps is unavailable

Do not replace it with Streamlit or a local-only deliverable.

Instead:

- complete the source code;
- build the frontend assets if possible;
- validate Python and frontend tests;
- document the exact Databricks Apps deployment procedure;
- record the unavailable workspace capability as a limitation;
- retain SQL/dashboard fallback assets.

## Quality gate

- frontend builds successfully;
- backend tests pass;
- API returns expected data;
- static frontend is served by Python;
- app deploys to Databricks Apps when available;
- deployed URL works;
- all core pages function without optional ML or Genie;
- README usage instructions are verified.

Report the deployed app location without exposing internal credentials and stop after Phase 6.

---

# Phase 7 — optional ML and Genie enhancements

Proceed only if the mandatory application is complete and stable.

Read `CLAUDE.md` and do not create dependencies from the core app to optional features.

## Optional ML

Create a simple baseline classification experiment using historical synthetic churn labels.

Compare:

- static attributes only;
- integrated behavior features from Customer 360;
- transparent rule-based prioritization.

Track relevant metrics such as precision, recall, ROC-AUC, and confusion matrix. Explain which metric matters for retention targeting and why.

Use MLflow if available. Do not add real-time serving unless it is clearly supported and adds value. Batch scores are sufficient.

The UI may show an optional “Model comparison” panel, but the core app must fall back to rule-based results.

## Optional Genie

If Genie is available:

- expose only curated Gold tables;
- add clear table and column descriptions;
- define business terms;
- configure and test a small set of known questions;
- document expected responses;
- provide a SQL/filter fallback.

Suggested questions:

- How many high-value customers are high risk?
- Show customers with both app and card engagement decline.
- Group high-risk customers by primary risk driver.
- How many high-risk customers still have salary deposits?

## Quality gate

- optional features do not break the mandatory app;
- model results are presented without inflated claims;
- Genie questions are tested;
- fallbacks are documented;
- optional status is clearly labeled.

Report additions and stop after Phase 7.

---

# Phase 8 — integration testing, deployment, and documentation

Read `CLAUDE.md` and test the full solution.

## Data tests

- rerun generation and transformations;
- verify row counts;
- verify uniqueness;
- verify score boundaries;
- verify driver/action consistency;
- verify KPI reconciliation.

## Backend tests

- health endpoint;
- successful responses;
- invalid query parameters;
- missing customer;
- SQL failure handling;
- response typing;
- pagination or row limits.

## Frontend tests

- navigation;
- loading state;
- empty state;
- error state;
- filter behavior;
- customer selection;
- mobile and desktop layout;
- accessibility basics.

## Deployment tests

- frontend production build;
- Python dependency installation;
- `app.yaml` command;
- Databricks Apps deployment;
- app restart after stopping;
- SQL warehouse/resource access;
- smoke test from the deployed URL.

## Required documentation

Complete:

- `README.md`;
- `docs/architecture.md`;
- `docs/demo-script.md`;
- `docs/data-dictionary.md`;
- `docs/free-edition-limitations.md`;
- `docs/poc-success-criteria.md`;
- troubleshooting section;
- app usage guide.

## Required limitations section

Document only limitations relevant to this demo:

- no real bank source connectivity;
- no automatic marketing-platform handoff;
- no mandatory real-time inference;
- no fully automated Next Best Action;
- no production-grade model serving requirement;
- Free Edition quota, uptime, and enterprise-control limitations.

## Quality gate

- all mandatory tests pass;
- no secrets are committed;
- deployed app is reachable when Apps is available;
- README steps are verified;
- the demo can run without optional features;
- limitations and synthetic assumptions are visible.

Provide a final test report and stop after Phase 8.

---

# Phase 9 — demo rehearsal and handoff

Read `CLAUDE.md` and the completed project documentation.

Prepare the solution for a ten-minute executive demo and technical Q&A.

## Ten-minute flow

Create and rehearse this flow:

### 0:00–1:00 — business context

Explain fragmented data, broad campaigns, and the goal of prioritizing high-value customers at risk.

### 1:00–3:00 — Executive Overview

Answer: Where should retention budget be focused?

### 3:00–5:00 — Segment Explorer

Answer: Which behavioral pattern should the campaign address?

### 5:00–7:00 — Customer 360

Answer: Why is this customer at risk and why act now?

### 7:00–9:00 — Retention Actions

Answer: Who should receive which action first?

### 9:00–10:00 — PoC and expansion

Explain what must be validated with bank data and how Customer 360 can later support cross-sell.

## Required handoff assets

- timed demo script;
- click path;
- three selected customer stories;
- expected KPI values;
- fallback path if the app, SQL warehouse, Genie, or optional ML is unavailable;
- technical Q&A notes;
- PoC success criteria;
- pre-demo checklist.

## Technical Q&A preparation

Prepare concise structured answers for:

- Why Databricks rather than another isolated model or dashboard?
- Why open table formats?
- Delta Lake versus Apache Iceberg.
- Why batch rather than real time for this phase?
- How would the app integrate with existing marketing tools?
- How would governance change in an enterprise workspace?
- What is synthetic and what must be validated in a PoC?

Use this answer structure:

1. conclusion;
2. meaning for the bank;
3. technical basis;
4. tradeoff or constraint;
5. how the PoC validates it.

## Pre-demo checklist

Include:

- restart Databricks App if stopped;
- verify SQL warehouse;
- run health endpoint;
- open and preload each page;
- verify the selected customer records;
- verify KPI totals;
- have SQL/dashboard fallback ready;
- do not depend on Genie or ML;
- confirm all simulated metrics are labeled.

## Quality gate

The phase is complete when the story can be delivered in ten minutes, all click paths are documented, and a fallback exists for every optional capability.

Provide the final handoff summary.

---

