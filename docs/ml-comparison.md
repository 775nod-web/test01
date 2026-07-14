# Optional ML comparison (Phase 7)

**This entire page describes an optional, Tier 2 enhancement. Nothing in
the mandatory demo (Phases 1–6) depends on it.** The core app always
falls back to the transparent rule-based score (`docs/risk-scoring.md`).
`churn_label_90d` is a **simulated ground-truth label** generated
alongside the archetypes in `notebooks/lib/datagen.py` — this comparison
tells us whether a simple model can recover the patterns the generator
built in, not whether either approach would work on real churn.

## What was compared

Three approaches to predicting `churn_label_90d`, all evaluated on the
**same held-out 30% test split** (2,400 of 8,000 synthetic customers) so
the comparison is apples-to-apples — an earlier draft of this comparison
evaluated the rule-based score on the full population while the ML models
only saw their test split, which inflated the rule's apparent
performance by construction; this was caught and fixed
(`notebooks/lib/ml_baseline.py`, `tests/test_ml_baseline.py`) before this
document was written.

| Approach | Features | Fitted? |
|---|---|---|
| Rule-based (mandatory) | The 8 signals in `docs/risk-scoring.md` | No — fixed thresholds and points |
| Static attributes only | `age_band`, `acquisition_channel`, `home_region`, `value_segment`, `tenure_months` | Yes — logistic regression |
| Integrated behavior features | All `customer_360` behavioral columns (balance/card/app/service/campaign trends) | Yes — logistic regression |

Model: scikit-learn `LogisticRegression` (`class_weight="balanced"`,
standardized features, fixed `random_state=42`) — a genuinely simple
baseline, not a tuned or ensembled model, matching the phase's own scope
("a simple baseline classification experiment").

## Results (8,000-customer run, held-out test set, n=2,400)

| Approach | Precision | Recall | ROC-AUC |
|---|---|---|---|
| Rule-based (mandatory) | 0.799 | 0.630 | 0.787 |
| Static attributes only | 0.421 | 0.528 | 0.514 |
| Integrated behavior features | 0.813 | **0.913** | **0.900** |

Confusion matrices (rows = actual, columns = predicted; order
`[[TN, FP], [FN, TP]]`):

- Rule-based: `[[1277, 154], [358, 611]]`
- Static attributes: `[[727, 704], [457, 512]]`
- Behavioral features: `[[1227, 204], [84, 885]]`

## Reading these results honestly

- **Static attributes alone carry almost no signal** (AUC 0.51, barely
  above the 0.50 random-guess line). This is by design — the generator
  ties churn to *behavior* archetypes, not to who a customer is
  demographically. This is a real and expected finding for this dataset,
  not evidence about real customers.
- **The rule-based score is a solid, honest baseline** (AUC 0.79) — it
  was designed by hand to capture exactly these behavioral signals, so
  this is close to a ceiling for what fixed thresholds can do without
  fitting.
- **The behavioral ML model recovers more signal than the fixed
  thresholds do**, particularly on recall (0.91 vs. 0.63) — it catches
  many more of the true churners in the held-out set, because it can
  weight continuous features rather than only counting whether they cross
  a fixed cutoff (e.g., a customer at -29% balance change gets zero rule
  points at the -30% threshold, but the ML model can still weight that
  closeness).

## Which metric matters for retention targeting, and why

**Recall matters more than precision here, but not without a limit.** A
missed at-risk customer (false negative) is a customer who churns without
ever being offered a retention action — once they leave, that revenue is
gone. A false positive just costs one unnecessary, low-cost outreach
touch (a push notification or a call-center script) to a customer who
was never actually going to leave. That asymmetry argues for prioritizing
recall.

But recall taken to its limit is the same as broad, un-targeted
campaigning — the exact problem this demo argues against (CLAUDE.md §3).
The right framing for a real PoC is **recall at a fixed, affordable
outreach capacity** (a precision-recall curve or "lift at top-K", not a
single threshold's recall), so the retention team can ask "if we can only
call 500 people this month, how many of our true churners do we catch?"
— see `docs/poc-success-criteria.md` for how this would be measured
against real outcomes.

## Reproducing this comparison

```bash
pip install -r requirements-dev.txt   # adds pandas, scikit-learn, mlflow-skinny
pytest tests/test_ml_baseline.py -v   # unit tests against a smaller sample
```

To rerun in Databricks with MLflow tracking (also optional, never a
dependency): `notebooks/07_optional_ml_baseline.py`, after Phases 2–4.
MLflow tracking URI is left to its default — Databricks notebooks route
`mlflow` to the workspace-hosted tracking server automatically; nothing in
this repo hardcodes a tracking URI.

## What this does not show

- Nothing about real bank customers or real churn — see
  `docs/poc-success-criteria.md`.
- Nothing about production model serving — this is a batch comparison,
  matching CLAUDE.md's "no mandatory real-time inference" constraint. The
  optional `gold.churn_model_scores` table (when the notebook is run) is a
  batch snapshot, not a serving endpoint.
- A tuned or production-grade model — this is intentionally the simplest
  useful baseline, per the phase's own scope.
