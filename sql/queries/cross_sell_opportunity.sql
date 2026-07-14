-- PoC & Future Expansion page — cross-sell reuse illustration ONLY
-- Business question: How could this same Customer 360 data support
-- cross-sell later? This is explicitly NOT a second demo use case
-- (CLAUDE.md #3) — it is one small, clearly-labeled illustrative query,
-- not a scored or ranked production feature.
--
-- Illustrates: low-risk, engaged customers with few products are a
-- plausible cross-sell audience — the same behavioral signals used for
-- retention (engagement, complaints, risk) generalize to a different
-- business question once reused.
-- Params: :limit (int)
SELECT
  c.customer_id,
  c.value_segment,
  c.product_count,
  c.app_engagement_score,
  c.complaint_count_90d,
  r.risk_segment
FROM {gold}.customer_360 c
JOIN {gold}.retention_action_list r ON r.customer_id = c.customer_id
WHERE r.risk_segment = 'Low'
  AND c.product_count <= 2
  AND c.app_engagement_score >= 70
  AND c.complaint_count_90d = 0
ORDER BY c.app_engagement_score DESC
LIMIT :limit;
