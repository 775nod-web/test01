-- Customer 360 page — monthly trend chart (balance, card, app, products)
-- Business question: What does this customer's behavior look like over
-- time, not just at a single point?
-- Params: :customer_id (text, required)
SELECT
  t.activity_month,
  t.eom_balance,
  t.avg_daily_balance,
  t.salary_deposit_flag,
  cu.card_spend_amount,
  cu.card_txn_count,
  cu.declined_txn_count,
  a.login_count,
  a.session_count,
  a.days_since_last_login_eom,
  p.product_count
FROM {silver}.account_transactions t
JOIN {silver}.card_usage cu
  ON cu.customer_id = t.customer_id AND cu.activity_month = t.activity_month
JOIN {silver}.app_activity a
  ON a.customer_id = t.customer_id AND a.activity_month = t.activity_month
JOIN {silver}.product_holdings p
  ON p.customer_id = t.customer_id AND p.activity_month = t.activity_month
WHERE t.customer_id = :customer_id
ORDER BY t.activity_month ASC;
