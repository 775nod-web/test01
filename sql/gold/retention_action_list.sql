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
-- estimated_value_at_risk is a labeled SIMULATED proxy
-- (simulated_annual_value x risk_score/129), not an actuarial estimate.
-- Every recommended action requires human review (CLAUDE.md #11) — this
-- table is decision support, not an automated financial decision.

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
ranked_drivers AS (
  SELECT
    *,
    array_sort(
      triggered_drivers,
      (a, b) -> CASE WHEN a.points > b.points THEN -1 WHEN a.points < b.points THEN 1 ELSE 0 END
    ) AS sorted_drivers
  FROM scored
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
)
SELECT
  customer_id,
  value_segment,
  simulated_annual_value,
  risk_score,
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
  ROUND(simulated_annual_value * (risk_score / 129.0), 2) AS estimated_value_at_risk,
  risk_score
    + CASE value_segment WHEN 'High' THEN 15 WHEN 'Medium' THEN 5 ELSE 0 END AS action_priority_score,
  RANK() OVER (
    ORDER BY risk_score + CASE value_segment WHEN 'High' THEN 15 WHEN 'Medium' THEN 5 ELSE 0 END DESC
  ) AS action_priority_rank
FROM segmented;
