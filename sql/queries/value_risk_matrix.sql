-- Executive Overview page — customer value vs. churn risk matrix
-- Business question: Are our highest-value customers also our highest-risk
-- customers, or are these independent dimensions? (CLAUDE.md requires risk
-- and value to be shown as separate axes, not a single blended score.)
-- Params: none.
SELECT
  value_segment,
  risk_segment,
  COUNT(*) AS customer_count,
  ROUND(SUM(estimated_value_at_risk), 2) AS estimated_value_at_risk_simulated
FROM {gold}.retention_action_list
GROUP BY value_segment, risk_segment
ORDER BY
  CASE value_segment WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END,
  CASE risk_segment WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END;
