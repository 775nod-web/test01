# Databricks Digital Bank Retention Demo — Claude Code Prompt Pack

This five-file package contains the instructions required for Claude Code to build an executive customer-retention demo on Databricks Free Edition.

## Files to upload to Claude Code

Upload these five files together:

```text
CLAUDE.md
README.md
00_MASTER_PROMPT.md
PHASES_01_TO_04.md
PHASES_05_TO_09.md
```

## Role of each file

### `CLAUDE.md`

Persistent project contract. It defines the business storyline, Databricks Free Edition constraints, required architecture, UI principles, mandatory features, optional features, quality standards, and prohibited implementation choices.

### `README.md`

Human-readable guide for using this prompt pack. Claude Code must also maintain the project-level README it creates during implementation.

### `00_MASTER_PROMPT.md`

Initial instruction for Claude Code. It tells the agent to inspect the environment, create a phased implementation plan, distinguish mandatory and optional capabilities, and start with Phase 1 only.

### `PHASES_01_TO_04.md`

Contains the mandatory data foundation:

1. Repository and environment setup.
2. Synthetic banking data.
3. Silver tables and Customer 360.
4. Explainable churn-risk scoring and retention actions.

### `PHASES_05_TO_09.md`

Contains analytics, application delivery, optional enhancements, testing, and handoff:

5. Dashboard and SQL assets.
6. React and Python application on Databricks Apps.
7. Optional machine learning and Genie enhancements.
8. Testing, deployment, and documentation.
9. Ten-minute demo rehearsal and handoff.

## Recommended first message to Claude Code

After uploading all five files, send this message:

```text
Read all five attached files before making any changes.

Treat CLAUDE.md as the highest-priority persistent project contract for this repository.
Use 00_MASTER_PROMPT.md as the execution instruction.
Use PHASES_01_TO_04.md and PHASES_05_TO_09.md as the ordered implementation specification.

Before implementation:
1. Identify contradictions, missing assumptions, or features that are unavailable in the current Databricks Free Edition workspace.
2. Present the planned repository structure.
3. Present a Phase 1–9 implementation plan.
4. Separate mandatory capabilities from optional capabilities.
5. Confirm the intended Databricks Apps deployment approach.

Then execute Phase 1 only.
Do not continue to Phase 2 until Phase 1 has passed its quality gate and you have reported the files created, checks performed, constraints, and unresolved issues.

For every phase:
- create or modify the actual project files;
- run appropriate tests or validation;
- correct discovered errors;
- update the project README and progress checklist;
- record anything that could not be implemented and why;
- stop at the phase quality gate and report the result.

Do not start optional ML, MLflow, Genie, or other Phase 7 work until the mandatory demo works end to end.

The final deliverable must run on Databricks Apps when that capability is available. A local-only application is not an acceptable final deliverable.
The frontend must use TypeScript and React.
The backend must use Python.
Do not use Streamlit.
Do not use Node.js or Express for backend APIs.
```

## Expected demo outcome

A marketing or CRM leader can:

- See the population of high-risk and high-value customers.
- Identify the most important churn-risk patterns.
- Drill into a unified Customer 360 view.
- Understand why an individual customer is prioritized.
- Review a transparent, human-reviewed retention action.
- Understand what would be tested in a PoC using bank data.
- See how the same Customer 360 can later be reused for cross-sell.

## Mandatory implementation

- Synthetic bank data generated inside Databricks.
- Bronze, Silver, and Gold Delta tables.
- Customer 360.
- Transparent rule-based risk score.
- Explainable risk drivers.
- Retention action list.
- Executive and operational visualizations.
- React and TypeScript frontend.
- Python backend, preferably FastAPI.
- Deployment to Databricks Apps when available.
- Complete app usage instructions.

## Optional implementation

- Machine-learning churn model.
- MLflow tracking.
- Genie.
- Lakeflow pipeline.
- Unity Catalog lineage walkthrough.

Optional capabilities must not be required for the ten-minute demo.

## Databricks Free Edition assumptions

The project is designed for a serverless, quota-limited Databricks Free Edition environment. Keep the data small and avoid real-time serving, online tables, external bank connectivity, enterprise identity configuration, and production security claims.

The final documentation must explain how to restart the Databricks App and verify the SQL warehouse before a demo.

## Required application architecture

```text
React + TypeScript frontend
          |
          | same-origin HTTP API
          v
Python FastAPI backend
          |
          | Databricks SQL or Databricks SDK
          v
Gold Delta tables in Unity Catalog
```

Node tooling may be used to build React. Node.js and Express must not be used for backend APIs. The Python application must serve the compiled React assets.

## Suggested application usage

1. Open the deployed Databricks Apps URL.
2. Start at **Executive Overview**.
3. Select the **High value / High risk** population.
4. Open **Segment Explorer** and apply behavioral filters.
5. Select a customer to open **Customer 360**.
6. Review risk drivers and the recommended action.
7. Open **Retention Actions** to see the prioritized campaign list.
8. Finish at **PoC & Future Expansion** to discuss validation criteria and cross-sell reuse.

## Demo safety

Before presenting:

- Restart the Databricks App if it has stopped.
- Verify the SQL warehouse is available.
- Run smoke tests.
- Preload all pages once.
- Keep a dashboard or SQL fallback available.
- Do not rely on Genie or an ML endpoint for the core storyline.

## Phase order

| Phase | Outcome |
|---|---|
| 1 | Repository and environment are ready |
| 2 | Synthetic source data exists |
| 3 | Silver tables and Customer 360 exist |
| 4 | Risk score and action list exist |
| 5 | Dashboard and SQL assets work |
| 6 | React/Python Databricks App is deployed |
| 7 | Optional ML and Genie enhancements |
| 8 | Tests, deployment, and documentation are complete |
| 9 | Ten-minute demo is rehearsed and handed off |

## Required final documentation from Claude Code

- Project `README.md`.
- `docs/demo-script.md`.
- `docs/data-dictionary.md`.
- `docs/free-edition-limitations.md`.
- `docs/poc-success-criteria.md`.
- `docs/architecture.md`.

## Success criteria

The project is successful when the complete business storyline works without optional capabilities and can be demonstrated in ten minutes from the deployed Databricks Apps URL.
