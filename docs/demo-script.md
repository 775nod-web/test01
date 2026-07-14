# Ten-minute demo script

Timed script, click path, expected values, and fallback plan for
presenting this demo to a CEO/CMO/CDO/CTO audience, per CLAUDE.md's fixed
storyline. Pair with `docs/technical-qa.md` for the Q&A that follows.

All figures below are from an actual 8,000-customer run
(`SEED=42`, the repo's default) — reproducible by rerunning Phases 2–4 in
your workspace with default widget values. If your workspace uses a
different customer count or seed, the same **shape** of story holds; only
the exact numbers will differ. The UI itself is Japanese by default (no
language toggle) — quoted "say" lines below are translated for this
document only.

**`CUST000001` is the fixed demo customer** — a deterministic, guaranteed
High-risk/High-value customer generated on every run regardless of seed or
scale (see `docs/risk-scoring.md` "Guaranteed Risk x Value distribution").
Use it as the reliable fallback for the Customer 360 section below if you
don't want to depend on which random customers are at-risk in your run.

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

**Say, pointing at the KPI tiles**: "8,000 customers. 140 are high risk —
under 2%. Of those, 27 are also high-value: our top priority. Today's
broad campaign would contact all 8,000 people; prioritizing narrows that
to 548 people — high risk with high/medium value, or medium risk with
high value — each with an action already assigned."

**Expected values** (8,000-customer default):

| KPI | Value |
|---|---|
| Total customers | 8,000 |
| High-risk customers | 140 (1.75%) |
| High-risk & high-value | 27 |
| Prioritized audience | 548 |
| Broad campaign audience | 8,000 |
| Estimated value at risk (simulated, total) | ~$987,500 |
| Estimated value at risk (simulated, high-risk only) | ~$101,100 |

**Point at the value-vs-risk matrix**: "Notice High-risk customers appear
in all three value tiers — 27 High-value, 50 Medium-value, 23 Low-value at
this scale. Risk and value are genuinely independent; a high-value
customer is not automatically safe, and a low-value customer is not
automatically ignorable."

**Point at Top Risk Drivers** (now scoped to the prioritized audience,
548 customers): name the top one or two bars — at this scale, "Balance
decline (90d)" (162) and "Card spend decline (90d)" (141) lead.

## 3:00–5:00 — Segment Explorer

**Business question**: Which customer behavior pattern should the
campaign address?

**Click path**: nav → Segment Explorer → click the "デジタル離反兆候"
(digital disengagement) preset, or check "Card spend decline" and "App
engagement decline" together.

**Say**: "Here's a concrete pattern: customers whose card spending *and*
app logins both dropped over 90 days — quietly disengaging before they
ever complain. At our scale that's 332 customers (verified in
`docs/genie-setup.md`, Q2). This is a specific, addressable segment, not
a vague 'at risk' bucket."

**Do**: click one customer row to transition into Customer 360. The
default preset shown on page load, "高価値・高リスク" (high-value/high-risk),
always includes `CUST000001` at or near the top.

## 5:00–7:00 — Customer 360

**Business question**: Why is this customer at risk, and how should we
respond?

**Click path**: (arrived via row click above), or use the "デモ用固定顧客
CUST000001 の Customer 360 を見る" link on Executive Overview, or navigate
directly to one of the customers in `docs/representative-customers.md`.

**Recommended customer for this slot**: `CUST000001` (the fixed demo
customer — high value, -45% balance / -47% card / -83% app engagement all
declining at once, one unresolved complaint on file — the clearest
multi-driver story, and it's guaranteed to exist on every run).

**Say, pointing at the risk score card**: "Risk score 64 out of 100 —
internally 83 out of 129, transparent points, not a black box. 5 of 8
signals detected. Primary driver: balance decline. Secondary: card spend
decline. Scroll down: balance, card, and app trends over the last 12
months, plus their actual contact history. Every recommendation is marked
'担当者による確認が必要' (human review required) — nothing here contacts a
customer automatically."

## 7:00–9:00 — Retention Actions

**Business question**: Who should receive which action first?

**Click path**: nav → Retention Actions (default: the full prioritized
audience, 548 customers at this scale — same figure as Executive
Overview's "優先施策対象" KPI and the CSV export).

**Say**: "This is the prioritized campaign list — ranked by a single
priority score combining risk, value, estimated value at risk, and
actionability, not risk alone. `CUST000001` sits at #3. Each row has a
specific action and channel: a card-benefit push for spend decline, a
call-center service recovery for unresolved contacts, a relationship
review for balance outflow. Every row requires human review. This list
can be filtered by risk or value segment, or exported as a CSV for the
campaign team — the CSV row count always matches the KPI tile."

**Do**: click "CSVをダウンロード" (Download CSV) once to show it works.

## 9:00–10:00 — PoC & Future Expansion

**Business question**: What do we need to validate before a production
decision?

**Click path**: nav → PoC & Future Expansion.

**Say**: "The top of this page is three things: what we'd confirm in a
PoC, the success criteria, and the immediate next action — agreeing
business goals, success criteria, target data, and environment in a PoC
design workshop. Below that, the same Customer 360 table extends directly
to cross-sell — not a second demo, just a reuse path, shown as one
illustrative query." *(Optionally, if asked)*: expand the two collapsed
sections — Free Edition/simulation details, and the optional ML
comparison, clearly labeled 任意 (optional) and never a dependency of the
core app.

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
      `CUST000001` (the fixed demo customer, guaranteed on every run) or
      any other ID from `docs/representative-customers.md`.
- [ ] Confirm the KPI totals on screen match this document (or note the
      actual numbers if your workspace used a different scale/seed).
- [ ] Have `sql/queries/*.sql` open in a SQL editor tab as a live fallback.
- [ ] Do not depend on the AI/BI Dashboard, Genie, or the optional ML
      panel being available — confirm the core five pages work without
      them.
- [ ] Confirm every simulated figure on screen still reads "simulated" —
      spot-check the Executive Overview value-at-risk tile and the
      Customer 360 estimated-value-at-risk field.
