-- Executive Overview page — top risk drivers chart
-- Business question: Which behavior pattern is most common among the
-- customers we're actually prioritizing for retention budget?
-- Params: none. Scoped to the canonical Prioritized Audience
-- (is_prioritized_audience = 1, sql/gold/retention_action_list.sql) rather
-- than every Medium/High risk customer, so this chart answers "what should
-- the prioritized campaign address" instead of a broader, less actionable
-- population.
SELECT
  primary_driver,
  COUNT(*) AS customer_count,
  ROUND(SUM(estimated_value_at_risk), 2) AS estimated_value_at_risk_simulated
FROM {gold}.retention_action_list
WHERE is_prioritized_audience = 1
GROUP BY primary_driver
ORDER BY customer_count DESC;
