# PoC success criteria

This demo proves the *decision flow* — unify data, score risk
transparently, explain drivers, recommend an action, keep a human in the
loop. It does not prove the flow works on real customers. This document
defines what a production PoC would need to validate, and by what
criteria, before a production decision.

## What must be validated with real bank data

- **Signal availability**: whether the 8 signals behind the risk score
  (`docs/risk-scoring.md`) — balance decline, card spend decline, app
  usage decline, long inactivity, complaints, unresolved contacts, stopped
  salary deposit, product decline — exist in real source systems, at a
  usable refresh cadence (daily/monthly), with acceptable completeness.
- **Threshold validity**: whether the point weights and High/Medium/Low
  cuts in `docs/risk-scoring.md` (tuned against synthetic archetypes) hold
  up against real historical churn, or need recalibration per portfolio,
  region, or customer segment.
- **Value metric**: whether `simulated_annual_value` should be replaced
  with an actual profitability, balance-based, or relationship-value
  metric already computed by finance/risk systems.
- **Data quality**: real source-system nulls, duplicates, and latency —
  the Bronze/Silver cleaning rules in `sql/silver/*.sql` are a template,
  not a finished data-quality spec for production sources.
- **Channel capacity and cost**: the real cost and throughput of call
  center, push/app, and email channels referenced in the action mapping —
  the demo assumes unlimited capacity.
- **Optional ML value**: whether the behavioral ML baseline's advantage
  over the rule-based score (`docs/ml-comparison.md`, measured only
  against a simulated label) replicates against real outcomes enough to
  justify the added operational complexity of a fitted model.

## Suggested PoC success metrics

| Metric | What it measures | Why it matters |
|---|---|---|
| **Lift** | Retention/response rate of the prioritized audience vs. today's broad campaign, over a real campaign cycle | Directly tests the core business claim: prioritization beats broad targeting |
| **Driver stability** | Whether the same primary driver keeps recurring for the same customer month over month, or churns noisily | A driver that flips randomly isn't explaining anything real |
| **Stakeholder adoption** | Whether marketing/CRM leaders actually use the driver + recommendation to choose an action, vs. reverting to broad campaigns | A technically correct model nobody uses has zero business value |
| **Operational fit** | Whether recommended actions map cleanly onto existing call-center/app/email workflows without new tooling | Determines real deployment cost beyond the model itself |
| **False-positive cost** | Share of flagged High-risk customers showing no real-world churn behavior in the following quarter | Every false positive spends a real outreach touch and risks annoying a stable customer |
| **Recall at capacity** | Of the customers the team can actually afford to contact this cycle, what share of true churners are caught | The metric that matters for retention targeting specifically — see `docs/ml-comparison.md` |

## Suggested PoC scope and timeline (illustrative, not a commitment)

1. **Weeks 1-2**: connect one real source system (e.g., account
   transactions) read-only; validate signal availability and data
   quality against the Bronze/Silver schema.
2. **Weeks 3-4**: backfill 6-12 months of history; compute the rule-based
   score against real data; compare its High/Medium/Low distribution to
   this demo's (`docs/risk-scoring.md` — 1.1% / 31.6% / 67.3% at
   8,000 synthetic customers) as a sanity check, not a target.
3. **Weeks 5-8**: run a real retention campaign cycle against the
   prioritized audience for a holdout-tested subset of customers; measure
   lift against a control group receiving the broad campaign.
4. **Week 9**: review lift, driver stability, and stakeholder adoption
   against the metrics above; decide whether to expand data sources,
   recalibrate thresholds, or proceed to a production build.

## Decision criteria: PoC → production

Proceed only if, at minimum:

- Lift is positive and large enough to justify the engineering cost of
  real source-system integration (not assumed here — measure it).
- Drivers are stable enough that a person can act on them with
  confidence, not noise.
- Marketing/CRM stakeholders actually adopted the workflow during the
  PoC, not just reviewed it once.
- No signal turned out to be systematically unavailable or unreliable in
  the real source systems.

If any of these fail, the right next step is usually to narrow scope
(fewer signals, one segment) and re-run a smaller PoC — not to scale the
current design as-is.

## What this PoC does not need to prove

Per `docs/free-edition-limitations.md`: real-time inference, a fully
automated Next Best Action, production-grade model serving, or automatic
hand-off to external marketing platforms. None of these are required to
validate the core business claim above.
