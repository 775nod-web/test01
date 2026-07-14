-- Customer 360 page — single customer summary
-- Business question: Why should this customer be prioritized, and how
-- should we respond?
-- Params: :customer_id (text, required)
SELECT
  c.customer_id,
  c.signup_date,
  c.tenure_months,
  c.age_band,
  c.acquisition_channel,
  c.home_region,
  c.value_segment,
  c.simulated_annual_value,
  c.current_balance,
  c.avg_balance_90d,
  c.balance_change_30d_pct,
  c.balance_change_90d_pct,
  c.transfer_out_amount_90d,
  c.salary_deposit_active,
  c.salary_deposit_stopped_flag,
  c.product_count,
  c.product_count_90d_ago,
  c.card_spend_90d,
  c.card_spend_change_30d_pct,
  c.card_spend_change_90d_pct,
  c.declined_txn_count_90d,
  c.days_since_last_login,
  c.login_count_90d,
  c.login_change_30d_pct,
  c.login_change_90d_pct,
  c.app_engagement_score,
  c.contact_count_90d,
  c.complaint_count_90d,
  c.unresolved_contacts_total,
  c.avg_satisfaction_score_90d,
  c.campaign_count_12m,
  c.campaign_response_rate_12m,
  c.campaign_conversion_rate_12m,
  r.risk_score,
  r.risk_segment,
  r.primary_driver,
  r.secondary_driver,
  r.recommended_action,
  r.recommended_channel,
  r.human_review_required,
  r.estimated_value_at_risk
FROM {gold}.customer_360 c
JOIN {gold}.retention_action_list r ON r.customer_id = c.customer_id
WHERE c.customer_id = :customer_id;
