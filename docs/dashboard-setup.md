# Dashboard and SQL assets (Phase 5)

## What was built

`sql/queries/*.sql` are the validated, parameterized query assets behind
the ten-minute storyline. Each file states its business question, its
parameters, and which page uses it:

| File | Page | Business question |
|---|---|---|
| `executive_overview.sql` | Executive Overview | Where should we focus limited retention budget? |
| `risk_distribution.sql` | Executive Overview (chart) | How many customers fall into each risk segment? |
| `value_risk_matrix.sql` | Executive Overview (chart) | Are risk and value the same thing, or independent? |
| `top_risk_drivers.sql` | Executive Overview (chart) | Which behavior pattern is most common among the Prioritized Audience (not just any at-risk customer)? |
| `segment_explorer.sql` | Segment Explorer | Which customer behavior pattern should the campaign address? |
| `customer_360_summary.sql` | Customer 360 | Why should this customer be prioritized, and how should we respond? |
| `customer_trends.sql` | Customer 360 (charts) | What does this customer's behavior look like over time? |
| `customer_contact_history.sql` | Customer 360 | What has this customer told us, and is it resolved? |
| `retention_actions.sql` | Retention Actions | Who should receive which action first? |
| `cross_sell_opportunity.sql` | PoC & Future Expansion | How could Customer 360 support cross-sell later (illustration only)? |

All ten queries are validated in `tests/test_dashboard_queries.py` against
a local Spark+Delta build of the real Bronze→Silver→Gold pipeline: KPI
totals reconcile with `executive_kpis`, filters return only matching rows,
pagination doesn't overlap, and the cross-sell query stays scoped to
low-risk/low-product/no-complaint customers as documented.

Queries use Spark's native named-parameter syntax (`:param_name`, bound via
`spark.sql(text, args={...})`). Phase 6's FastAPI backend will bind these
the same way (Databricks SQL connector/SDK) or adapt the placeholder style
if the chosen driver requires a different convention — that's a small,
low-risk mechanical change, not a logic change.

## AI/BI Dashboard: why it isn't included as a build artifact here

CLAUDE.md's own instruction for this phase is conditional: *"If AI/BI
dashboard creation is available and stable, create it. In all cases, save
the underlying SQL queries so the Databricks App can use them."*

This build has no network path to any Databricks workspace (see
`docs/free-edition-limitations.md`), so I cannot confirm Lakeview/AI-BI
dashboard availability, and I cannot test a hand-authored dashboard
definition against a real workspace before handing it off. Shipping an
untested dashboard JSON file risks looking "done" while silently failing
to import. The SQL query layer above is the verified, working deliverable;
building the dashboard itself is a short manual step for you, described
below.

## Manual steps to build the AI/BI Dashboard (optional, ~15 minutes)

1. In your Databricks workspace, confirm a SQL warehouse is running and
   Phases 2–4 have been run (Gold tables exist).
2. Go to **Dashboards → Create dashboard**.
3. For each file in `sql/queries/`, add a new dataset using that file's SQL
   (paste the query text; the `{gold}`/`{silver}` placeholders should be
   replaced with your actual resolved schema — check the notebook output
   from Phase 2–4 for the exact values, e.g. `bank_demo.gold` or
   `bank_demo_gold`).
4. Add visualizations per the table above: KPI counters for
   `executive_overview.sql`; a bar chart for `risk_distribution.sql`; a
   heatmap/table for `value_risk_matrix.sql`; a bar chart for
   `top_risk_drivers.sql`.
5. Label every simulated figure (`estimated_value_at_risk*`,
   `simulated_annual_value`) as **Simulated** in the visualization title or
   a text tile, per CLAUDE.md's labeling requirement.
6. Save and note the dashboard URL for the Phase 9 demo handoff.

This dashboard is a **convenience view for stakeholders who prefer
clicking over an app** — the mandatory, tested deliverable is the React +
FastAPI application (Phase 6), which calls these same queries directly and
does not depend on this dashboard existing.
