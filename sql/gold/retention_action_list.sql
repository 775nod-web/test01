-- Gold: retention_action_list
-- One row per customer (superset — not just High risk) so the Retention
-- Actions page can filter/sort and Customer 360 can join drivers/action
-- for any customer. Risk scoring is a transparent, configurable point
-- system (CLAUDE.md #10) — NOT a predictive model. Point values are
-- distinct on purpose so ranking by points alone resolves primary vs.
-- secondary driver without a separate tie-break rule.
--
-- Signal          | Threshold                          | Points
-- Balance decline | balance_change_90d_pct <= -30%      | 26
-- Salary stopped   | salary_deposit_stopped_flag = 1     | 24
-- Card spend decl. | card_spend_change_90d_pct <= -30%   | 20
-- App usage decl.  | login_change_90d_pct <= -50%        | 18
-- Complaint incr.  | complaint_count_90d >= 2             | 14
-- Long inactivity  | days_since_last_login >= 30          | 10
-- Unresolved contact | unresolved_contacts_total >= 1     | 9
-- Product decline  | product_count_change_90d < 0         | 8
-- Max possible score: 129
--
-- risk_segment: High >= 40, Medium 15-39, Low < 15 (see
-- docs/risk-scoring.md for the empirical distribution behind these cuts).
--
-- risk_score_normalized_100 is a display-only ROUND(risk_score / 129 * 100)
-- projection for the UI ("risk score 72 / 100") — the internal 129-point
-- scale and its thresholds above remain the source of truth everywhere
-- else (docs/risk-scoring.md documents the exact correspondence).
-- triggered_signal_count is how many of the 8 signals below fired
-- ("5 / 8 signals detected"), for the same display purpose.
--
-- estimated_value_at_risk is a labeled SIMULATED proxy
-- (simulated_annual_value x risk_score/129), not an actuarial estimate.
-- Every recommended action requires human review (CLAUDE.md #11) — this
-- table is decision support, not an automated financial decision.
--
-- action_priority_score / action_priority_rank / priority_tier — an
-- additive, normalized weighted-sum score combining the four factors the
-- UI names ("churn risk, customer value, estimated value at risk,
-- actionability"). An additive scorecard was chosen over a multiplicative
-- alternative after comparing both on real generated data: it is the more
-- explainable pattern for a business audience (a plain weighted sum, like
-- a familiar lead-scoring model), no single factor dominates the ranking,
-- and it still puts High-risk/High-value customers at the top while
-- letting Medium-risk/High-value customers outrank High-risk/Low-value
-- ones — see docs/risk-scoring.md "Priority ranking formula" for the full
-- comparison and rationale.
--
--   priority_score = 0.40 * (risk_score / 129)
--                   + 0.30 * value_weight        (High=1.0, Medium=0.6, Low=0.3)
--                   + 0.20 * value_at_risk_norm   (estimated_value_at_risk / population max)
--                   + 0.10 * actionability_weight (1.0 if salary deposits are still active, else 0.7)
--
-- action_priority_rank is a unique ROW_NUMBER() (never tied). priority_tier
-- splits the same ordering into three even bands (A = top third, most
-- urgent, C = bottom third) via NTILE(3). The UI never shows this formula
-- directly — only the fixed sentence in docs/risk-scoring.md.
--
-- is_prioritized_audience is the single, canonical definition of "the
-- prioritized campaign" used everywhere it's counted (Executive Overview's
-- KPI tile, Retention Actions' default list and CSV export, and Top Risk
-- Drivers' population) so those counts always reconcile exactly:
--   (High risk AND High/Medium value) OR (Medium risk AND High value)
--   AND an action was actually assigned (recommended_action is set)
--   AND human_review_required = 1 (the actionability check)
-- This synthetic model has no account-closure/attrition flag, so "not
-- fully churned" is not separately encoded — every generated customer is,
-- by construction, still an active customer. A real deployment would add
-- that condition here once such a flag exists in source data.

DROP TABLE IF EXISTS {gold}.retention_action_list;

CREATE TABLE {gold}.retention_action_list
USING DELTA
AS
WITH flags AS (
  SELECT
    customer_id,
    value_segment,
    simulated_annual_value,
    CASE WHEN balance_change_90d_pct <= -0.30 THEN 1 ELSE 0 END AS balance_decline_flag,
    CASE WHEN salary_deposit_stopped_flag = 1 THEN 1 ELSE 0 END AS salary_stopped_flag,
    CASE WHEN card_spend_change_90d_pct <= -0.30 THEN 1 ELSE 0 END AS card_spend_decline_flag,
    CASE WHEN login_change_90d_pct <= -0.50 THEN 1 ELSE 0 END AS app_usage_decline_flag,
    CASE WHEN complaint_count_90d >= 2 THEN 1 ELSE 0 END AS complaint_increase_flag,
    CASE WHEN days_since_last_login >= 30 THEN 1 ELSE 0 END AS long_inactivity_flag,
    CASE WHEN unresolved_contacts_total >= 1 THEN 1 ELSE 0 END AS unresolved_contact_flag,
    CASE WHEN product_count_change_90d < 0 THEN 1 ELSE 0 END AS product_decline_flag
  FROM {gold}.customer_360
),
scored AS (
  SELECT
    *,
    (balance_decline_flag * 26)
      + (salary_stopped_flag * 24)
      + (card_spend_decline_flag * 20)
      + (app_usage_decline_flag * 18)
      + (complaint_increase_flag * 14)
      + (long_inactivity_flag * 10)
      + (unresolved_contact_flag * 9)
      + (product_decline_flag * 8) AS risk_score,
    filter(
      array(
        named_struct('driver', 'Balance decline (90d)', 'points', balance_decline_flag * 26),
        named_struct('driver', 'Salary deposit stopped', 'points', salary_stopped_flag * 24),
        named_struct('driver', 'Card spend decline (90d)', 'points', card_spend_decline_flag * 20),
        named_struct('driver', 'App engagement decline (90d)', 'points', app_usage_decline_flag * 18),
        named_struct('driver', 'Rising complaints', 'points', complaint_increase_flag * 14),
        named_struct('driver', 'Long app inactivity', 'points', long_inactivity_flag * 10),
        named_struct('driver', 'Unresolved service contact', 'points', unresolved_contact_flag * 9),
        named_struct('driver', 'Product holding decreased', 'points', product_decline_flag * 8)
      ),
      x -> x.points > 0
    ) AS triggered_drivers
  FROM flags
),
signal_counted AS (
  SELECT
    *,
    size(triggered_drivers) AS triggered_signal_count,
    ROUND(risk_score / 129.0 * 100) AS risk_score_normalized_100
  FROM scored
),
ranked_drivers AS (
  SELECT
    *,
    array_sort(
      triggered_drivers,
      (a, b) -> CASE WHEN a.points > b.points THEN -1 WHEN a.points < b.points THEN 1 ELSE 0 END
    ) AS sorted_drivers
  FROM signal_counted
),
segmented AS (
  SELECT
    *,
    CASE
      WHEN risk_score >= 40 THEN 'High'
      WHEN risk_score >= 15 THEN 'Medium'
      ELSE 'Low'
    END AS risk_segment,
    COALESCE(sorted_drivers[0].driver, 'No material risk driver') AS primary_driver,
    CASE WHEN size(sorted_drivers) >= 2 THEN sorted_drivers[1].driver ELSE 'None' END AS secondary_driver
  FROM ranked_drivers
),
actioned AS (
  SELECT
    *,
    -- Actions/channels are only assigned for Medium/High risk. A Low-risk
    -- customer with one weak, isolated signal (e.g. a single unresolved
    -- contact) does not warrant a retention campaign action.
    CASE
      WHEN risk_segment = 'Low' THEN 'No immediate action'
      ELSE
        CASE primary_driver
          WHEN 'Unresolved service contact' THEN 'Priority service recovery'
          WHEN 'Rising complaints' THEN 'Fee/service-plan review'
          WHEN 'Card spend decline (90d)' THEN 'Targeted card benefit message'
          WHEN 'App engagement decline (90d)' THEN 'Personalized in-app engagement message'
          WHEN 'Long app inactivity' THEN 'Personalized in-app engagement message'
          WHEN 'Balance decline (90d)' THEN 'Relationship review (balance outflow)'
          WHEN 'Salary deposit stopped' THEN 'Relationship review (income change)'
          WHEN 'Product holding decreased' THEN 'Product/portfolio review'
          ELSE 'No immediate action'
        END
    END AS recommended_action,
    CASE
      WHEN risk_segment = 'Low' THEN 'None'
      ELSE
        CASE primary_driver
          WHEN 'Unresolved service contact' THEN 'Call Center'
          WHEN 'Rising complaints' THEN 'Call Center'
          WHEN 'Card spend decline (90d)' THEN 'Push/App'
          WHEN 'App engagement decline (90d)' THEN 'Push/App'
          WHEN 'Long app inactivity' THEN 'Push/App'
          WHEN 'Balance decline (90d)' THEN 'Call Center'
          WHEN 'Salary deposit stopped' THEN 'Call Center'
          WHEN 'Product holding decreased' THEN 'Email'
          ELSE 'None'
        END
    END AS recommended_channel,
    CASE
      WHEN risk_segment IN ('High', 'Medium') THEN 1  -- a human must review before any outreach
      ELSE 0
    END AS human_review_required,
    ROUND(simulated_annual_value * (risk_score / 129.0), 2) AS estimated_value_at_risk
  FROM segmented
),
audience_flagged AS (
  SELECT
    *,
    CASE
      WHEN (
        (risk_segment = 'High' AND value_segment IN ('High', 'Medium'))
        OR (risk_segment = 'Medium' AND value_segment = 'High')
      )
      AND recommended_action != 'No immediate action'
      AND human_review_required = 1
      THEN 1
      ELSE 0
    END AS is_prioritized_audience
  FROM actioned
),
priority_scored AS (
  SELECT
    *,
    CASE value_segment WHEN 'High' THEN 1.0 WHEN 'Medium' THEN 0.6 ELSE 0.3 END AS value_weight,
    CASE WHEN salary_stopped_flag = 1 THEN 0.7 ELSE 1.0 END AS actionability_weight,
    estimated_value_at_risk / NULLIF(MAX(estimated_value_at_risk) OVER (), 0) AS value_at_risk_norm
  FROM audience_flagged
),
priority_final AS (
  SELECT
    *,
    0.40 * (risk_score / 129.0)
      + 0.30 * value_weight
      + 0.20 * COALESCE(value_at_risk_norm, 0)
      + 0.10 * actionability_weight AS action_priority_score
  FROM priority_scored
),
ranked_priority AS (
  SELECT
    *,
    ROW_NUMBER() OVER (ORDER BY action_priority_score DESC, customer_id ASC) AS action_priority_rank,
    NTILE(3) OVER (ORDER BY action_priority_score DESC, customer_id ASC) AS priority_tier_bucket
  FROM priority_final
)
SELECT
  customer_id,
  value_segment,
  simulated_annual_value,
  risk_score,
  risk_score_normalized_100,
  triggered_signal_count,
  risk_segment,
  primary_driver,
  secondary_driver,
  balance_decline_flag,
  salary_stopped_flag,
  card_spend_decline_flag,
  app_usage_decline_flag,
  complaint_increase_flag,
  long_inactivity_flag,
  unresolved_contact_flag,
  product_decline_flag,
  recommended_action,
  recommended_channel,
  human_review_required,
  estimated_value_at_risk,
  is_prioritized_audience,
  action_priority_score,
  action_priority_rank,
  CASE priority_tier_bucket WHEN 1 THEN 'A' WHEN 2 THEN 'B' ELSE 'C' END AS priority_tier
FROM ranked_priority;
