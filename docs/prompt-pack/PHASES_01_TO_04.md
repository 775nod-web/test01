# Phases 01 to 04 — Core data foundation and retention logic

> Execute these phases in order. Stop at each quality gate, test the outputs, update README.md, and report unresolved issues before continuing.

# Phase 1 — repository and environment

Read `CLAUDE.md` and the current project README.

Prepare the project for a Databricks Free Edition implementation.

## Tasks

1. Inspect the current repository and workspace files.
2. Determine the available catalog, default schema, serverless notebook compute, SQL warehouse, Databricks Apps access, and relevant permissions.
3. Create the agreed project directory structure.
4. Create or update the project-level `README.md` with:
   - purpose;
   - architecture;
   - prerequisites;
   - Free Edition constraints;
   - phase checklist;
   - planned app usage;
   - restart guidance for Databricks Apps.
5. Create configuration files with safe placeholders:
   - Python dependency file;
   - frontend package files;
   - TypeScript configuration;
   - Vite configuration;
   - `app.yaml` template;
   - `.gitignore`.
6. Create documentation placeholders under `docs/`.
7. Define a small-data target suitable for Free Edition, for example 5,000 to 20,000 customers and 6 to 12 months of aggregated activity.
8. Document detected feature availability. Do not guess.

## Architecture requirements

Use React + TypeScript for the frontend and FastAPI for the backend. Plan to serve the compiled React bundle from FastAPI. The production runtime command must start the Python backend on `0.0.0.0` using `DATABRICKS_APP_PORT`.

Do not run or present a local application as the final deployment.

## Quality gate

Phase 1 is complete only when:

- the project structure exists;
- the project README is useful;
- dependencies and configuration are defined;
- no secrets or hardcoded workspace-specific IDs are committed;
- Databricks Apps availability is documented;
- the next steps can be executed from Databricks.

Report the results and stop after Phase 1.

---

# Phase 2 — synthetic banking data

Read `CLAUDE.md`, the project README, and Phase 1 outputs.

Create deterministic synthetic data inside Databricks. Do not download external data.

## Required domains

- customers
- account_transactions
- card_usage
- app_activity
- contact_history
- product_holdings
- campaign_history

## Data design

Create realistic but non-sensitive synthetic patterns. Never generate real-looking card numbers, bank-account numbers, addresses, government identifiers, or personal contact details.

The generated data must include intentional patterns so the demo is explainable:

- some high-value customers experience balance decline;
- some customers show simultaneous card and app engagement decline;
- some customers have increasing complaints or unresolved contacts;
- some customers stop salary deposits;
- a smaller population has strong retention signals;
- historical churn labels may be generated for optional ML validation.

Use a fixed random seed and document the generation logic.

## Required outputs

- Rerunnable notebook or Python script for generation.
- Bronze Delta tables.
- Row-count and distribution checks.
- Data dictionary updates.
- A data-quality report showing duplicates, nulls, ranges, and class balance.

## Recommended scale

Keep the scale safe for Free Edition. Prefer aggregated daily or monthly activity over event-level billions of rows.

## Quality gate

Phase 2 is complete only when:

- generation is deterministic;
- all required domains exist;
- patterns are visible in summary queries;
- no sensitive-looking identifiers exist;
- tables can be recreated without manual cleanup;
- documentation is updated.

Report validation results and stop after Phase 2.

---

# Phase 3 — Silver layer and Customer 360

Read `CLAUDE.md` and validate Phase 2 outputs.

Build clean Silver tables and the mandatory Gold Customer 360 table.

## Silver requirements

For each domain:

- enforce types;
- remove or resolve duplicates;
- standardize dates and categorical values;
- apply explicit null-handling rules;
- validate customer IDs;
- add data-quality status where useful.

## Customer 360 requirements

Create one row per customer with features including:

### Customer value

- value segment;
- tenure;
- product count;
- average balance;
- simulated annual value or revenue, clearly labeled.

### Account behavior

- 30-day and 90-day balance change;
- transfer-out behavior;
- salary-deposit status.

### Card behavior

- spending and frequency change;
- declined-transaction count.

### App behavior

- login and session change;
- days since last login;
- engagement score.

### Service behavior

- contact count;
- complaint count;
- unresolved contacts;
- sentiment or satisfaction proxy if generated.

### Campaign behavior

- prior contact frequency;
- prior response and conversion indicators.

## Required outputs

- Silver transformation scripts or notebooks.
- `bank_demo.gold.customer_360` or an environment-compatible equivalent.
- Reconciliation queries.
- Column descriptions and data dictionary.
- At least three representative customer profiles selected for the later demo.

## Quality gate

- one row per customer;
- no unexplained duplicate customer IDs;
- derived metrics reconcile with source data;
- values are plausible;
- representative customer stories are explainable;
- all logic is rerunnable.

Report validation results and stop after Phase 3.

---

# Phase 4 — explainable risk score and retention actions

Read `CLAUDE.md` and validate Customer 360.

Implement the mandatory transparent prioritization logic. Do not describe it as a machine-learning prediction model.

## Risk scoring

Use configurable point contributions for signals such as:

- 90-day balance decline;
- card-spend decline;
- app-engagement decline;
- days since last login;
- complaint increase;
- unresolved contact;
- stopped salary deposit;
- reduced product holdings.

Generate:

- risk score;
- High, Medium, or Low risk segment;
- primary risk driver;
- secondary risk driver;
- driver contribution details;
- action priority combining risk and customer value.

Ensure high-risk customers are not simply the highest-value customers. Risk and value are separate dimensions.

## Retention recommendations

Use transparent business rules to recommend:

- fee or service-plan review;
- priority service recovery;
- card-benefit reminder;
- app-engagement message;
- relationship review for balance outflow;
- no immediate action where appropriate.

Add:

- recommended action;
- recommended channel;
- human-review-required flag;
- simulated estimated value at risk.

## Required outputs

- `retention_action_list` Gold table.
- `executive_kpis` Gold table or views.
- Unit-style SQL or Python tests for boundary conditions.
- Documentation explaining every score and action rule.
- A comparison between broad campaign audience and prioritized audience.

## Quality gate

- every high-risk record has an explainable driver;
- action logic is consistent with the driver;
- totals reconcile;
- simulated estimates are labeled;
- no automated financial decision is implied;
- Human-in-the-loop is explicit.

Report validation results and stop after Phase 4.

---

