# Ten-minute demo script

Timed script, click path, expected values, and fallback plan for
presenting this demo to a CEO/CMO/CDO/CTO audience, per CLAUDE.md's fixed
storyline. Pair with `docs/technical-qa.md` for the Q&A that follows.

All figures below are from an actual 8,000-customer run
(`SEED=42`, the repo's default) — reproducible by rerunning Phases 2–4 in
your workspace with default widget values. If your workspace uses a
different customer count or seed, the same **shape** of story holds; only
the exact numbers will differ.

## 0:00–1:00 — Business context

**Say**: "Our customer data is fragmented across app activity, accounts,
cards, loans, contacts, products, and campaigns. Today's retention
campaigns are broad and uniform — they miss real churn signals, cost more
than they need to, and can annoy customers who were never at risk. This
demo shows a Customer 360 view that identifies who's actually at risk,
explains why in plain language, and recommends a human-reviewed action —
built entirely on Databricks Free Edition, using synthetic data."

**Do**: nothing on screen yet — this is scene-setting.

## 1:00–3:00 — Executive Overview

**Business question**: Where should we focus limited retention budget?

**Click path**: open the deployed app URL → land on Executive Overview
(default page).

**Say, pointing at the KPI tiles**: "8,000 customers. 89 are high risk —
just over 1%. Of those, 7 are also high-value: our top priority. Today's
broad campaign would contact all 8,000 people; a prioritized campaign
narrows that to 56 people who are both at-risk and worth retaining."

**Expected values** (8,000-customer default):

| KPI | Value |
|---|---|
| Total customers | 8,000 |
| High-risk customers | 89 (1.1%) |
| High-risk & high-value | 7 |
| Prioritized audience (high-risk, high/medium-value) | 56 |
| Broad campaign audience | 8,000 |
| Estimated value at risk (simulated, total) | ~$924,500 |
| Estimated value at risk (simulated, high-risk only) | ~$43,900 |

**Point at the value-vs-risk matrix**: "Notice High-risk customers appear
in all three value tiers — 7 High-value, 49 Medium-value, 33 Low-value.
Risk and value are genuinely independent; a high-value customer is not
automatically safe, and a low-value customer is not automatically
ignorable."

**Point at Top Risk Drivers**: name the top one or two bars (typically
"Unresolved service contact" and "Rising complaints" at this scale).

## 3:00–5:00 — Segment Explorer

**Business question**: Which customer behavior pattern should the
campaign address?

**Click path**: nav → Segment Explorer → check "Card spend decline" and
"App engagement decline" together.

**Say**: "Here's a concrete pattern: customers whose card spending *and*
app logins both dropped over 90 days — quietly disengaging before they
ever complain. At our scale that's 292 customers (verified in
`docs/genie-setup.md`, Q2). This is a specific, addressable segment, not
a vague 'at risk' bucket."

**Do**: click one customer row to transition into Customer 360.

## 5:00–7:00 — Customer 360

**Business question**: Why is this customer at risk, and how should we
respond?

**Click path**: (arrived via row click above, or navigate directly to one
of the five customers in `docs/representative-customers.md`).

**Recommended customer for this slot**: `CUST000090` (high value,
-40.4% balance change over 90 days, no complaints — the cleanest single-
driver story) or `CUST006272` (high value, salary deposit stopped,
-29.75% balance change).

**Say, pointing at the risk score card**: "Risk score 55 out of 129 —
transparent points, not a black box. Primary driver: card spend decline.
Secondary: app engagement decline. Scroll down: balance, card, and app
trends over the last 12 months, plus their actual contact history. Every
recommendation is marked 'Human review required' — nothing here contacts
a customer automatically."

## 7:00–9:00 — Retention Actions

**Business question**: Who should receive which action first?

**Click path**: nav → Retention Actions (default filter: High + Medium
risk, all values).

**Say**: "This is the prioritized campaign list — ranked by risk and
value together, not risk alone. Each row has a specific action and
channel: a card-benefit push for spend decline, a call-center service
recovery for unresolved contacts, a relationship review for balance
outflow. Every row requires human review. This list can be filtered by
risk or value segment, or exported as a CSV for the campaign team."

**Do**: click "Download CSV" once to show it works.

## 9:00–10:00 — PoC & Future Expansion

**Business question**: What do we need to validate before a production
decision?

**Click path**: nav → PoC & Future Expansion.

**Say**: "Everything here is synthetic — clearly labeled throughout the
app. Before a production decision, we'd validate these exact signals
against real source systems, measure real lift against a control group,
and confirm the thresholds hold up against real churn — see the success
criteria and metrics here. The same Customer 360 table also extends
directly to cross-sell — not a second demo, just a reuse path, shown here
as one illustrative query." *(Optionally, if asked)*: point at the
"Model comparison" panel, clearly labeled optional, and note the app
never depends on it.

## Fallback plan

| If unavailable | Fallback |
|---|---|
| Databricks App won't start / is stopped | Restart per README; if still down, walk through screenshots taken during rehearsal, or run the SQL queries in `sql/queries/` directly in a SQL editor |
| SQL warehouse not running | Start it (Compute → SQL Warehouses); the app's `/api/health` will show `data_mode` and fail loudly rather than silently, so check it first |
| AI/BI Dashboard not built/unstable | Not part of the core demo — skip silently, use the app instead (`docs/dashboard-setup.md`) |
| Genie not configured/unstable | Not part of the core demo — use Segment Explorer's filters or the SQL in `docs/genie-setup.md` instead |
| Optional ML panel missing or wrong | Not part of the core demo — skip silently; the app always shows the rule-based score regardless |
| A specific customer ID 404s | Use a different one from `docs/representative-customers.md` — don't debug live |

## Technical Q&A

See `docs/technical-qa.md` for structured answers to the seven expected
questions (Databricks vs. isolated tooling, open table formats, Delta vs.
Iceberg, batch vs. real-time, marketing-tool integration, enterprise
governance, synthetic vs. PoC validation).

## Pre-demo checklist

- [ ] Restart the Databricks App if it shows Stopped (README → "Restarting
      the Databricks App").
- [ ] Verify the attached SQL warehouse is Running.
- [ ] Hit `/api/health` on the deployed URL — confirm
      `{"status":"ok","data_mode":"databricks"}` (not `"local"`).
- [ ] Open and click through all five pages once, end to end.
- [ ] Confirm the customer(s) you plan to show in Customer 360 exist —
      search by ID from `docs/representative-customers.md`.
- [ ] Confirm the KPI totals on screen match this document (or note the
      actual numbers if your workspace used a different scale/seed).
- [ ] Have `sql/queries/*.sql` open in a SQL editor tab as a live fallback.
- [ ] Do not depend on the AI/BI Dashboard, Genie, or the optional ML
      panel being available — confirm the core five pages work without
      them.
- [ ] Confirm every simulated figure on screen still reads "simulated" —
      spot-check the Executive Overview value-at-risk tile and the
      Customer 360 estimated-value-at-risk field.
