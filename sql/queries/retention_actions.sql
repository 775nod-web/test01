-- Retention Actions page — prioritized campaign list
-- Business question: Who should receive which action first?
--
-- Params (all optional except :limit/:offset):
--   :risk_segment    text, e.g. 'High' | 'Medium' — pass NULL for both
--   :value_segment   text, e.g. 'High' | 'Medium' | 'Low' — pass NULL for all
--   :limit           int, page size
--   :offset          int, page offset
--
-- Excludes Low risk / "No immediate action" rows by default — this page
-- is the campaign list, not the full customer base (use Segment Explorer
-- for the full base).
SELECT
  customer_id,
  value_segment,
  risk_segment,
  risk_score,
  primary_driver,
  secondary_driver,
  recommended_action,
  recommended_channel,
  human_review_required,
  estimated_value_at_risk,
  action_priority_rank
FROM {gold}.retention_action_list
WHERE risk_segment IN ('High', 'Medium')
  AND (:risk_segment IS NULL OR risk_segment = :risk_segment)
  AND (:value_segment IS NULL OR value_segment = :value_segment)
ORDER BY action_priority_rank ASC
LIMIT :limit OFFSET :offset;
