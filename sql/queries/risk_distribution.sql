-- Executive Overview page — risk distribution chart
-- Business question: How many customers fall into each risk segment, and
-- how severe is each segment on average?
-- Params: none.
SELECT
  risk_segment,
  COUNT(*) AS customer_count,
  ROUND(AVG(risk_score), 1) AS avg_risk_score
FROM {gold}.retention_action_list
GROUP BY risk_segment
ORDER BY
  CASE risk_segment WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END;
