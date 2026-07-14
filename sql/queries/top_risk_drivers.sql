-- Executive Overview page — top risk drivers chart
-- Business question: Which behavior pattern is driving the most at-risk
-- customers, across the whole book?
-- Params: none. Excludes customers with no material driver (Low risk with
-- no triggered signal) since they are not part of the "why are people at
-- risk" story.
SELECT
  primary_driver,
  COUNT(*) AS customer_count,
  ROUND(SUM(estimated_value_at_risk), 2) AS estimated_value_at_risk_simulated
FROM {gold}.retention_action_list
WHERE primary_driver != 'No material risk driver'
GROUP BY primary_driver
ORDER BY customer_count DESC;
