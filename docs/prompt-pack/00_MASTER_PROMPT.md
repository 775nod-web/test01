# Master prompt — build the complete demo

You are a senior Databricks solution architect and full-stack engineer. Build an executive-quality digital-bank customer-retention demo in the current Databricks Free Edition workspace.

Read and obey `CLAUDE.md` before doing any work. Treat it as the persistent project contract.

## Objective

Create a demo in which a CRM or marketing leader can:

1. View high-risk and high-value customers.
2. identify the behavior patterns driving risk.
3. inspect a Customer 360 record.
4. understand transparent risk drivers.
5. review a recommended human-approved retention action.
6. see what a PoC would validate using real bank data.
7. understand that the same Customer 360 can later be reused for cross-sell.

## Mandatory product behavior

The core demo must use synthetic data and must work without machine learning, Genie, model serving, real-time processing, or external systems.

Use a transparent rule-based prioritization score for the mandatory version. Machine learning and Genie are optional enhancements only.

## Required technology

- Databricks Free Edition.
- Delta tables in Bronze, Silver, and Gold layers.
- Unity Catalog-compatible naming.
- Frontend: TypeScript + React.
- Backend: Python, preferably FastAPI.
- No Streamlit.
- No Node.js or Express backend.
- Final application deployed to Databricks Apps when available.
- React must be built into static assets served by the Python application.

## Required views

- Executive Overview.
- Segment Explorer.
- Customer 360.
- Retention Actions.
- PoC and Future Expansion.

## Required business framing

Every page must answer a business question. Every technical feature must be connected to a business decision and outcome.

Do not claim that synthetic metrics are actual business benefits. Label all estimated value and outcome figures as simulated.

## Execution

Work phase by phase using `PHASES_01_TO_04.md` and `PHASES_05_TO_09.md`.

For this initial run:

1. Inspect the project and Databricks environment.
2. Create a progress checklist mapped to all phases.
3. Identify which capabilities are available in this Free Edition workspace, including Databricks Apps.
4. Do not substitute local-only application hosting for Databricks Apps.
5. Begin Phase 1 only.
6. At the end, report files created, checks performed, available capabilities, constraints, and the next phase.


## Five-file execution contract

Before changing code, read all five supplied files. Resolve instructions using this priority order:

1. `CLAUDE.md`
2. `00_MASTER_PROMPT.md`
3. The active phase section in `PHASES_01_TO_04.md` or `PHASES_05_TO_09.md`
4. `README.md`

Execute only one phase at a time. At the end of each phase, run its quality gate, update the project README and progress checklist, report created or modified files, list tests and validation performed, record unavailable capabilities or unresolved issues, and stop for review.

Do not begin Phase 7 until the mandatory Tier 1 application works end to end.
