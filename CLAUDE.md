# CLAUDE.md

## 1. Project mission

Build a polished executive demo for a digital-native bank on Databricks Free Edition.

The demo must show how fragmented customer data can be converted into actionable retention decisions:

1. Unify customer data into a Customer 360 view.
2. Identify high-risk and high-value customers.
3. Explain why each customer is considered at risk.
4. Recommend a human-reviewed retention action.
5. Show how the same Customer 360 can later support cross-sell use cases.

The goal is not to showcase as many Databricks features as possible. The goal is to demonstrate a credible business decision flow that can lead to a PoC.

## 2. Target audience and communication style

The audience includes CEO, CMO, CDO, CTO, and business leaders.

All outputs must:

- Start with the business question and outcome, not the product feature.
- Connect every technical component to an operational decision and business value.
- Be understandable to a Databricks beginner.
- Remain technically defensible when questioned by architects or engineers.
- Use a confident, peer-level, professional tone without excessive deference.
- Avoid exaggerated or unsupported claims.
- Clearly label simulated values, synthetic data, assumptions, and estimates.

## 3. Fixed demo storyline

The primary use case is customer retention, not cross-sell.

The fixed storyline is:

- Current state: customer data is fragmented across app activity, accounts, cards, loans, contacts, products, and campaigns.
- Business problem: broad, uniform campaigns miss churn signals, increase cost, and degrade customer experience.
- Target state: a marketing leader identifies high-value customers with elevated churn risk, understands the risk drivers, and selects an appropriate retention action.
- Future expansion: reuse the same Customer 360 for cross-sell and personalization.

Do not turn cross-sell into a second primary demo objective. Mention it only as a reuse path and future phase.

## 4. Databricks Free Edition constraints

Design and implement for Databricks Free Edition.

Assume:

- Serverless-only compute.
- One 2X-Small SQL warehouse.
- Fair-use quotas and no SLA.
- A maximum of three Databricks Apps per account.
- Apps may stop automatically after up to 24 hours and must be restartable.
- No SSO, SCIM, private networking, online tables, or production-grade enterprise controls.
- No real bank connectivity or customer data.
- Outbound internet access may be restricted.

Therefore:

- Use synthetic data generated inside Databricks.
- Keep data volume small enough for Free Edition.
- Avoid unnecessary external packages and network calls.
- Prefer batch processing over real-time processing.
- Do not require online tables, real-time serving, external marketing systems, or enterprise identity features.
- Keep all SQL and transformations deterministic and rerunnable.
- Do not present Free Edition as production-ready or appropriate for commercial operation.

## 5. Required implementation tiers

### Tier 1: mandatory and demo-safe

The demo must work with only these components:

- Synthetic banking data.
- Bronze, Silver, and Gold Delta tables.
- Customer 360 Gold table.
- Rule-based churn risk scoring.
- Explainable primary and secondary risk drivers.
- Retention action list.
- Executive dashboard or equivalent visualizations.
- A customer detail view.
- A PoC transition screen or section.

### Tier 2: optional enhancement

Implement only after Tier 1 works end to end:

- Machine-learning churn model.
- MLflow experiment tracking.
- Genie natural-language analysis.
- Lakeflow pipeline.
- Unity Catalog lineage demonstration.

Tier 2 must never be a dependency for the core demo. Provide a fallback when an optional feature is unavailable or unstable.

## 6. Application architecture when Databricks Apps is available

The final application must be deployed to Databricks Apps. Do not treat a local web server as the final deliverable.

Required stack:

- Frontend: TypeScript + React.
- Backend: Python.
- Do not use Streamlit.
- Do not use Node.js or Express as the backend.
- Recommended Python API framework: FastAPI.
- Build the React frontend into static assets and serve those assets from the Python application.
- Use Node tooling only to build the React frontend, not to provide backend APIs.
- Use Databricks SQL or the Databricks SDK from the Python backend to query Gold tables.
- Configure execution with `app.yaml`.
- Bind to `0.0.0.0` and the `DATABRICKS_APP_PORT` provided by the runtime.
- Store no secrets in source files.
- Make the app usable after deployment from the Databricks Apps URL.

Recommended layout:

```text
project-root/
├── app.yaml
├── requirements.txt
├── package.json
├── CLAUDE.md
├── README.md
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── db.py
│   ├── schemas.py
│   └── services/
├── frontend/
│   ├── src/
│   ├── public/
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
├── notebooks/
├── sql/
├── tests/
└── docs/
```

The build may copy `frontend/dist` into a directory served by FastAPI. The production command must start only the Python application.

If Databricks Apps is not available in the workspace, finish the data layer, SQL assets, dashboard specification, and app source code, and document the exact deployment steps and the unavailable feature. Do not replace the final application with Streamlit or a local-only app.

## 7. UI and visual design

Use a polished executive design inspired by Google-style presentation principles:

- Light background.
- Soft, vivid accent colors.
- Large numerical KPIs.
- Clear visual hierarchy.
- Generous whitespace.
- One key message per section.
- Minimal borders and visual noise.
- Concise labels and tooltips.
- Accessible contrast and keyboard navigation.

Suggested palette:

- Blue: `#4285F4`
- Green: `#34A853`
- Yellow: `#FBBC04`
- Red: `#EA4335`
- Light blue surface: `#E8F0FE`
- Light green surface: `#E6F4EA`
- Light yellow surface: `#FEF7E0`
- Light red surface: `#FCE8E6`
- Main text: `#202124`
- Secondary text: `#5F6368`
- Page background: `#F8F9FA`

Do not use every color at once. Use red only for risk or negative changes, green for positive outcomes, blue for primary actions, and yellow for warnings or attention.

## 8. Required application pages

The application should contain these pages or clearly separated views:

### Executive Overview

Show:

- Total customers.
- High-risk customers.
- High-risk and high-value customers.
- Estimated value at risk, clearly marked as simulated.
- Current broad-campaign audience versus prioritized audience.
- Risk distribution.
- Customer value versus churn risk matrix.
- Top risk drivers.

Business question: Where should we focus limited retention budget?

### Segment Explorer

Allow filtering by:

- Risk segment.
- Customer value segment.
- Product holdings.
- Balance decline.
- Card spend decline.
- App engagement decline.
- Contact or complaint increase.

Business question: Which customer behavior pattern should the campaign address?

### Customer 360

Show one customer's:

- Value and tenure.
- Product holdings.
- Balance and transaction trend.
- Card usage trend.
- App usage trend.
- Contact and complaint history.
- Risk score.
- Primary and secondary drivers.
- Recommended action and channel.

Business question: Why should this customer be prioritized, and how should we respond?

### Retention Actions

Show:

- Prioritized target list.
- Risk score and segment.
- Value segment.
- Main driver.
- Recommended action.
- Recommended channel.
- Estimated value at risk.

Include CSV download only if it can be implemented safely and reliably.

Business question: Who should receive which action first?

### PoC and Future Expansion

Show:

- What is synthetic in the demo.
- What must be tested with bank data.
- Suggested PoC success metrics.
- Features not implemented in Free Edition.
- How Customer 360 extends to cross-sell.

Business question: What do we need to validate before a production decision?

## 9. Data model

Use a catalog and schema pattern equivalent to:

```text
bank_demo.bronze
bank_demo.silver
bank_demo.gold
```

Required source domains:

- customers
- account_transactions
- card_usage
- app_activity
- contact_history
- product_holdings
- campaign_history

Required Gold tables:

- `customer_360`
- `retention_action_list`
- `executive_kpis`
- optional `churn_model_scores`

Use synthetic customer identifiers only. Never generate real-looking account numbers, card numbers, addresses, or sensitive identifiers.

## 10. Rule-based risk scoring

The mandatory risk score must be transparent and configurable.

Suggested signals:

- Balance decrease greater than 30 percent over 90 days.
- Card spending decrease greater than 30 percent over 90 days.
- App usage decrease greater than 50 percent.
- Long days since last login.
- Two or more complaints in 90 days.
- At least one unresolved contact.
- Salary deposit stopped.
- Product holding decreased.

Store:

- Total score.
- Risk segment: High, Medium, Low.
- Primary driver.
- Secondary driver.
- Driver-level score contributions.

Do not claim the rule-based score is a predictive model. Call it a transparent prioritization score.

## 11. Retention recommendation logic

Use transparent business rules for the mandatory version.

Examples:

- Fee complaint -> fee review or service-plan discussion by call center.
- Unresolved contact -> priority service recovery by call center.
- Card-spend decline -> targeted card benefit message.
- App-engagement decline -> personalized in-app education or benefit reminder.
- Balance outflow -> relationship review or deposit benefit discussion.

Recommendations are decision support, not automated financial advice. Keep a human in the loop.

## 12. Testing and quality gates

Do not mark a phase complete until its checks pass.

Required checks:

- All scripts rerun without manual cleanup.
- Synthetic data has intentional, explainable churn patterns.
- No primary-key duplicates in Silver customer data.
- Gold tables contain one row per customer where expected.
- Risk score and drivers are internally consistent.
- Dashboard totals reconcile with table queries.
- API endpoints return typed, documented payloads.
- Empty and error states are handled in the UI.
- No secrets, tokens, or warehouse IDs are committed.
- App starts with the documented Databricks command.
- Core demo works without Genie or ML.
- README instructions have been executed and verified.

## 13. Documentation requirements

Maintain:

- `README.md` with setup, deployment, usage, demo flow, troubleshooting, limitations, and architecture.
- `docs/demo-script.md` with a timed ten-minute script.
- `docs/data-dictionary.md`.
- `docs/free-edition-limitations.md`.
- `docs/poc-success-criteria.md`.

The README must explain how to use the application after deployment.

## 14. Working method

For each phase:

1. Inspect the existing repository before changing files.
2. State assumptions briefly.
3. Implement only the current phase.
4. Run validations.
5. Update the README and progress checklist.
6. Report created files, tests run, results, and unresolved constraints.
7. Do not silently skip failures.

Avoid broad refactors unrelated to the current phase.

## 15. Definition of done

The project is done when:

- The synthetic data pipeline runs in Databricks Free Edition.
- Customer 360 and retention tables are queryable.
- The rule-based core demo is fully functional.
- The React and Python application is deployed to Databricks Apps when Apps is available.
- The app can be used from the deployed Databricks Apps URL.
- The ten-minute storyline can be completed without optional features.
- Free Edition omissions are clearly documented.
- Cross-sell is shown as a future reuse case, not a second demo.
- README and all required documentation are complete.
