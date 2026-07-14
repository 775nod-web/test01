-- Gold: customer_360
-- One row per customer, unifying all Silver domains. "30-day" and "90-day"
-- changes are approximated as month-over-month and 3-months-over-3-months
-- comparisons, since source data is aggregated monthly (documented in
-- docs/data-dictionary.md and docs/free-edition-limitations.md) rather than
-- daily/event-level. Customers with fewer than 4 months of history (new
-- customers) get NULL 90-day comparisons rather than a misleading number —
-- this is an explicit null-handling rule, not missing data.
--
-- simulated_annual_value is a labeled simulated figure, not a real
-- financial metric. churn_label_90d is carried through only for optional
-- Phase 7 ML validation and must not be read by the Phase 4 rule-based
-- risk score.

DROP TABLE IF EXISTS {gold}.customer_360;

CREATE TABLE {gold}.customer_360
USING DELTA
AS
WITH txn_ranked AS (
  SELECT *,
    ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY activity_month DESC) AS rn
  FROM {silver}.account_transactions
),
txn_latest AS (SELECT * FROM txn_ranked WHERE rn = 1),
txn_30d AS (SELECT * FROM txn_ranked WHERE rn = 2),
txn_90d AS (SELECT * FROM txn_ranked WHERE rn = 4),
txn_90d_agg AS (
  SELECT customer_id,
    AVG(eom_balance) AS avg_balance_90d,
    SUM(transfer_out_amount) AS transfer_out_amount_90d
  FROM txn_ranked WHERE rn <= 3
  GROUP BY customer_id
),
salary_history AS (
  SELECT customer_id,
    MAX(CASE WHEN rn = 1 THEN salary_deposit_flag END) AS salary_deposit_active,
    MAX(CASE WHEN rn > 1 THEN salary_deposit_flag END) AS salary_deposit_was_active_before
  FROM txn_ranked
  GROUP BY customer_id
),

card_ranked AS (
  SELECT *,
    ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY activity_month DESC) AS rn
  FROM {silver}.card_usage
),
card_latest AS (SELECT * FROM card_ranked WHERE rn = 1),
card_30d AS (SELECT * FROM card_ranked WHERE rn = 2),
card_90d AS (SELECT * FROM card_ranked WHERE rn = 4),
card_90d_agg AS (
  SELECT customer_id,
    SUM(card_spend_amount) AS card_spend_90d,
    SUM(declined_txn_count) AS declined_txn_count_90d
  FROM card_ranked WHERE rn <= 3
  GROUP BY customer_id
),

app_ranked AS (
  SELECT *,
    ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY activity_month DESC) AS rn
  FROM {silver}.app_activity
),
app_latest AS (SELECT * FROM app_ranked WHERE rn = 1),
app_30d AS (SELECT * FROM app_ranked WHERE rn = 2),
app_90d AS (SELECT * FROM app_ranked WHERE rn = 4),
app_90d_agg AS (
  SELECT customer_id, SUM(login_count) AS login_count_90d
  FROM app_ranked WHERE rn <= 3
  GROUP BY customer_id
),
app_engagement AS (
  SELECT customer_id, login_count_90d,
    ROUND(PERCENT_RANK() OVER (ORDER BY login_count_90d) * 100, 1) AS app_engagement_score
  FROM app_90d_agg
),

product_ranked AS (
  SELECT *,
    ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY activity_month DESC) AS rn
  FROM {silver}.product_holdings
),
product_latest AS (SELECT * FROM product_ranked WHERE rn = 1),
product_90d AS (SELECT * FROM product_ranked WHERE rn = 4),

contact_90d AS (
  SELECT customer_id,
    COUNT(*) AS contact_count_90d,
    SUM(is_complaint) AS complaint_count_90d,
    ROUND(AVG(satisfaction_score), 2) AS avg_satisfaction_score_90d
  FROM {silver}.contact_history
  WHERE contact_date > DATE_SUB((SELECT MAX(activity_month) FROM {silver}.account_transactions), 90)
  GROUP BY customer_id
),
contact_unresolved AS (
  SELECT customer_id, SUM(1 - is_resolved) AS unresolved_contacts_total
  FROM {silver}.contact_history
  GROUP BY customer_id
),

campaign_12m AS (
  SELECT customer_id,
    COUNT(*) AS campaign_count_12m,
    ROUND(AVG(responded_flag), 3) AS campaign_response_rate_12m,
    ROUND(AVG(converted_flag), 3) AS campaign_conversion_rate_12m
  FROM {silver}.campaign_history
  GROUP BY customer_id
)

SELECT
  c.customer_id,
  c.signup_date,
  c.tenure_months,
  c.age_band,
  c.acquisition_channel,
  c.home_region,
  c.customer_value_segment AS value_segment,
  c.simulated_annual_value,
  c.churn_label_90d,

  -- account behavior
  ROUND(txn_latest.eom_balance, 2) AS current_balance,
  ROUND(txn_90d_agg.avg_balance_90d, 2) AS avg_balance_90d,
  ROUND(
    (txn_latest.eom_balance - txn_30d.eom_balance) / NULLIF(txn_30d.eom_balance, 0), 4
  ) AS balance_change_30d_pct,
  ROUND(
    (txn_latest.eom_balance - txn_90d.eom_balance) / NULLIF(txn_90d.eom_balance, 0), 4
  ) AS balance_change_90d_pct,
  ROUND(txn_90d_agg.transfer_out_amount_90d, 2) AS transfer_out_amount_90d,
  salary_history.salary_deposit_active,
  CASE
    WHEN salary_history.salary_deposit_active = 0
     AND salary_history.salary_deposit_was_active_before = 1
    THEN 1 ELSE 0
  END AS salary_deposit_stopped_flag,

  -- product holdings
  product_latest.product_count,
  product_90d.product_count AS product_count_90d_ago,
  (product_latest.product_count - product_90d.product_count) AS product_count_change_90d,

  -- card behavior
  ROUND(card_90d_agg.card_spend_90d, 2) AS card_spend_90d,
  ROUND(
    (card_latest.card_spend_amount - card_30d.card_spend_amount) / NULLIF(card_30d.card_spend_amount, 0), 4
  ) AS card_spend_change_30d_pct,
  ROUND(
    (card_latest.card_spend_amount - card_90d.card_spend_amount) / NULLIF(card_90d.card_spend_amount, 0), 4
  ) AS card_spend_change_90d_pct,
  card_90d_agg.declined_txn_count_90d,

  -- app behavior
  app_latest.days_since_last_login_eom AS days_since_last_login,
  app_90d_agg.login_count_90d,
  ROUND(
    (app_latest.login_count - app_30d.login_count) / NULLIF(app_30d.login_count, 0), 4
  ) AS login_change_30d_pct,
  ROUND(
    (app_latest.login_count - app_90d.login_count) / NULLIF(app_90d.login_count, 0), 4
  ) AS login_change_90d_pct,
  app_engagement.app_engagement_score,

  -- service behavior
  COALESCE(contact_90d.contact_count_90d, 0) AS contact_count_90d,
  COALESCE(contact_90d.complaint_count_90d, 0) AS complaint_count_90d,
  COALESCE(contact_unresolved.unresolved_contacts_total, 0) AS unresolved_contacts_total,
  contact_90d.avg_satisfaction_score_90d,

  -- campaign behavior
  COALESCE(campaign_12m.campaign_count_12m, 0) AS campaign_count_12m,
  COALESCE(campaign_12m.campaign_response_rate_12m, 0.0) AS campaign_response_rate_12m,
  COALESCE(campaign_12m.campaign_conversion_rate_12m, 0.0) AS campaign_conversion_rate_12m

FROM {silver}.customers c
LEFT JOIN txn_latest ON txn_latest.customer_id = c.customer_id
LEFT JOIN txn_30d ON txn_30d.customer_id = c.customer_id
LEFT JOIN txn_90d ON txn_90d.customer_id = c.customer_id
LEFT JOIN txn_90d_agg ON txn_90d_agg.customer_id = c.customer_id
LEFT JOIN salary_history ON salary_history.customer_id = c.customer_id
LEFT JOIN card_latest ON card_latest.customer_id = c.customer_id
LEFT JOIN card_30d ON card_30d.customer_id = c.customer_id
LEFT JOIN card_90d ON card_90d.customer_id = c.customer_id
LEFT JOIN card_90d_agg ON card_90d_agg.customer_id = c.customer_id
LEFT JOIN app_latest ON app_latest.customer_id = c.customer_id
LEFT JOIN app_30d ON app_30d.customer_id = c.customer_id
LEFT JOIN app_90d ON app_90d.customer_id = c.customer_id
LEFT JOIN app_90d_agg ON app_90d_agg.customer_id = c.customer_id
LEFT JOIN app_engagement ON app_engagement.customer_id = c.customer_id
LEFT JOIN product_latest ON product_latest.customer_id = c.customer_id
LEFT JOIN product_90d ON product_90d.customer_id = c.customer_id
LEFT JOIN contact_90d ON contact_90d.customer_id = c.customer_id
LEFT JOIN contact_unresolved ON contact_unresolved.customer_id = c.customer_id
LEFT JOIN campaign_12m ON campaign_12m.customer_id = c.customer_id
WHERE c.data_quality_status = 'valid';
