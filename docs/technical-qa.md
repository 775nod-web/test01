# Technical Q&A notes

Structured answers for the seven questions CLAUDE.md/Phase 9 expect from
architects and engineers in the room. Each follows: **conclusion → what
it means for the bank → technical basis → tradeoff/constraint → how the
PoC validates it.**

## 1. Why Databricks rather than another isolated model or dashboard?

**Conclusion**: because the value here is one platform carrying data from
raw ingestion through a governed feature layer to a decision-support UI —
not a single model or a single chart.

**For the bank**: a standalone churn model or a standalone BI dashboard
each solve one step. Neither owns the Bronze→Silver→Gold pipeline that
makes the Customer 360 table trustworthy, reusable for cross-sell later,
and auditable end to end.

**Technical basis**: this demo's Bronze/Silver/Gold layering, Unity
Catalog-compatible naming, and SQL-first transformations
(`sql/silver/*.sql`, `sql/gold/*.sql`) are ordinary Lakehouse patterns —
the same governed tables back the rule-based score, the optional ML
comparison, and the API, with no duplicated logic between them.

**Tradeoff**: this concentrates risk on one platform choice and requires
the team to standardize on it; a smaller point solution has a lower
initial adoption cost but doesn't extend to a second use case
(cross-sell) without rebuilding the data layer.

**PoC validates**: whether the same Gold tables genuinely serve a second
use case later (`docs/poc-success-criteria.md`'s cross-sell reuse note)
without re-engineering — that's the platform bet this question is really
about.

## 2. Why open table formats?

**Conclusion**: so the data isn't locked to one query engine or one
vendor's runtime.

**For the bank**: Gold tables can be read by Databricks SQL, Spark jobs,
or (with the right connector) other engines, without exporting or
duplicating data — important if the bank already has other analytics
tooling.

**Technical basis**: this demo writes Delta Lake tables — an open,
Parquet-based format with a transaction log — via plain `CREATE TABLE ...
USING DELTA` (see any `sql/silver/*.sql` file). Nothing here uses a
proprietary storage format.

**Tradeoff**: open formats mean the bank owns more of the
operationalization (compaction, vacuuming, access control at the
lakehouse layer) rather than relying on a fully managed proprietary
system — Free Edition further limits this to serverless-managed
defaults, not hand-tuned storage.

**PoC validates**: whether the bank's existing governance/tooling can
actually read these tables directly, which is the main practical benefit
open formats promise.

## 3. Delta Lake versus Apache Iceberg

**Conclusion**: this demo uses Delta Lake because it's the native,
zero-configuration format on Databricks Free Edition; Iceberg is a
credible alternative worth evaluating for a multi-engine PoC, not a
technical rejection.

**For the bank**: if the bank's broader data estate already standardized
on Iceberg (e.g., for multi-engine interoperability with non-Databricks
tools), that's a legitimate reason to pilot Iceberg tables instead — the
SQL and API layers in this repo don't depend on which one is used.

**Technical basis**: both are open, ACID, Parquet-based table formats
with transaction logs and time travel. Delta Lake is deepest-integrated
with Databricks (Unity Catalog, serverless SQL, Delta Live
Tables/Lakeflow); Iceberg has broader multi-engine adoption elsewhere
(Snowflake, Trino, etc.) and Databricks does support reading/writing
Iceberg tables via UniForm.

**Tradeoff**: choosing Delta here is a Free-Edition pragmatism choice
(works out of the box, well-documented, this demo's SQL is portable Delta
DDL) — not evidence that Iceberg is unsuitable for the bank's real
architecture.

**PoC validates**: if the bank has a genuine multi-engine requirement,
pilot the same Gold table shapes on both formats and compare operational
overhead, not just feature checklists.

## 4. Why batch rather than real time for this phase?

**Conclusion**: because the business decision this demo supports — who to
prioritize for a retention campaign — doesn't need sub-second latency,
and Free Edition explicitly has no mandatory real-time serving tier.

**For the bank**: a campaign decision made from data that's a day or a
week old is still far better than today's broad, undifferentiated
campaigns. Real-time churn scoring would matter for a different use case
(e.g., blocking a fraudulent transaction), not this one.

**Technical basis**: all Gold tables are rebuilt by rerunning notebooks
(`notebooks/01-04`), and the risk score and retention list are batch SQL
(`sql/gold/retention_action_list.sql`) — no streaming source, no
model-serving endpoint anywhere in this repo.

**Tradeoff**: batch means risk scores can be stale by up to one refresh
cycle; for a slow-moving behavioral signal (90-day balance trend), that's
an acceptable tradeoff against the operational complexity of streaming
infrastructure Free Edition doesn't provide anyway.

**PoC validates**: what refresh cadence the retention team actually needs
in practice (daily vs. weekly vs. monthly) — likely far looser than
real-time, but that's a business question to confirm, not assume.

## 5. How would the app integrate with existing marketing tools?

**Conclusion**: today, through the CSV export on the Retention Actions
page; a real integration would replace that with an API/file hand-off
into the bank's actual campaign platform.

**For the bank**: the demo deliberately stops at "a prioritized,
human-reviewed list ready for outreach" — CLAUDE.md is explicit that
automated hand-off to external marketing systems is out of scope for Free
Edition.

**Technical basis**: `GET /api/retention-actions/export` returns a CSV
with customer ID, risk/value segment, driver, action, channel, and
estimated value at risk — the same shape a marketing platform's bulk
import would expect.

**Tradeoff**: manual export means a human step between "the model
recommends" and "the campaign fires" — which is a feature, not a gap,
given CLAUDE.md's human-in-the-loop requirement, but it does mean no
automatic feedback loop (did the campaign work?) without further
integration work.

**PoC validates**: whether the bank's actual marketing platform can
consume this CSV shape directly, or needs a defined API/ETL contract —
and whether campaign response data can flow back into `campaign_history`
to close the loop.

## 6. How would governance change in an enterprise workspace?

**Conclusion**: Unity Catalog access controls, lineage, and audit logging
— all present in enterprise Databricks — are simply unavailable or
limited on Free Edition; nothing in this demo's design blocks adopting
them.

**For the bank**: production deployment would add row/column-level
security on customer PII, audit logs of who queried what, and formal data
classification — none of which exist in this Free Edition build because
the platform tier doesn't support them, not because the design excludes
them.

**Technical basis**: this demo already uses Unity Catalog-compatible
three-level naming (`catalog.schema.table`) where available, falling
back to Hive metastore only when UC isn't enabled
(`notebooks/lib/catalog_utils.py`) — the naming convention is
forward-compatible with enterprise UC governance without any table
redesign.

**Tradeoff**: Free Edition has no SSO/SCIM, no private networking, and no
production-grade enterprise controls (CLAUDE.md §4) — this demo is
explicitly not presented as production-ready anywhere in its
documentation.

**PoC validates**: which governance controls the bank's actual
compliance/security requirements demand before any real customer data
touches these tables — this must be answered before Phase 2's synthetic
generator is ever pointed at real data.

## 7. What is synthetic, and what must be validated in a PoC?

**Conclusion**: every row in every table is synthetic
(`notebooks/lib/datagen.py`, fixed seed); nothing here is a claim about
real customers.

**For the bank**: the credible claim is the *decision flow* — unify
fragmented data, score risk transparently, explain drivers, recommend a
human-reviewed action. The credible claim is *not* "this exact risk score
will find your real churners."

**Technical basis**: `docs/poc-success-criteria.md` lists exactly what
must be validated with real data — signal availability, threshold
recalibration, a real value metric, real data quality, real channel
capacity — and `docs/free-edition-limitations.md` lists what Free Edition
itself cannot prove (enterprise governance, production SLA, real-time
serving).

**Tradeoff**: synthetic data lets this demo exist at all without any real
customer data exposure risk, but means every number on screen — KPI
totals, risk distributions, the optional ML AUC — describes the
generator's own design, not real churn behavior.

**PoC validates**: literally everything in
`docs/poc-success-criteria.md`'s "what must be validated" and "success
metrics" sections — that document is the direct answer to this question,
not a separate concern.
