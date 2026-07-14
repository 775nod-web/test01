-- Retention Actions page — prioritized campaign list
-- Business question: Who should receive which action first?
--
-- Params (all optional except :limit/:offset):
--   :risk_segment    text, e.g. 'High' | 'Medium' — pass NULL for both
--   :value_segment   text, e.g. 'High' | 'Medium' | 'Low' — pass NULL for all
--   :limit           int, page size
--   :offset          int, page offset
--
-- Defaults to the canonical Prioritized Audience (is_prioritized_audience = 1,
-- defined once in sql/gold/retention_action_list.sql) — the same flag
-- Executive Overview's KPI tile and Top Risk Drivers use, so this page's
-- default (unfiltered) row count and CSV export row count always match
-- Executive Overview's "Prioritized audience" figure exactly. The
-- risk/value filters narrow within that audience; they do not expand it.
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
  action_priority_rank,
  priority_tier
FROM {gold}.retention_action_list
WHERE is_prioritized_audience = 1
  AND (:risk_segment IS NULL OR risk_segment = :risk_segment)
  AND (:value_segment IS NULL OR value_segment = :value_segment)
ORDER BY action_priority_rank ASC
LIMIT :limit OFFSET :offset;
