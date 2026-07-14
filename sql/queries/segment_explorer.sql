-- Segment Explorer page — filterable customer list
-- Business question: Which customer behavior pattern should the campaign
-- address?
--
-- Params (all optional — pass NULL/None to skip a filter):
--   :risk_segment              text, e.g. 'High' | 'Medium' | 'Low'
--   :value_segment             text, e.g. 'High' | 'Medium' | 'Low'
--   :max_product_count         int, keeps customers with product_count <= this
--   :balance_decline_pct       double, e.g. -0.30 keeps balance_change_90d_pct <= this
--   :card_spend_decline_pct    double, e.g. -0.30 keeps card_spend_change_90d_pct <= this
--   :app_decline_pct           double, e.g. -0.50 keeps login_change_90d_pct <= this
--   :min_complaints_90d        int, keeps complaint_count_90d >= this
--   :limit                     int, row cap (always pass one — see Phase 6 API notes)
--
-- Uses Spark's native parameterized-query syntax (`spark.sql(text, args=...)`),
-- validated locally in tests/test_segment_explorer.py. Phase 6 finalizes the
-- exact bind-parameter mechanism for whichever Python driver is used.
SELECT
  c.customer_id,
  c.value_segment,
  r.risk_segment,
  r.risk_score,
  r.primary_driver,
  c.product_count,
  c.balance_change_90d_pct,
  c.card_spend_change_90d_pct,
  c.login_change_90d_pct,
  c.complaint_count_90d,
  c.unresolved_contacts_total,
  r.recommended_action,
  r.recommended_channel
FROM {gold}.customer_360 c
JOIN {gold}.retention_action_list r ON r.customer_id = c.customer_id
WHERE (:risk_segment IS NULL OR r.risk_segment = :risk_segment)
  AND (:value_segment IS NULL OR c.value_segment = :value_segment)
  AND (:max_product_count IS NULL OR c.product_count <= :max_product_count)
  AND (:balance_decline_pct IS NULL OR c.balance_change_90d_pct <= :balance_decline_pct)
  AND (:card_spend_decline_pct IS NULL OR c.card_spend_change_90d_pct <= :card_spend_decline_pct)
  AND (:app_decline_pct IS NULL OR c.login_change_90d_pct <= :app_decline_pct)
  AND (:min_complaints_90d IS NULL OR c.complaint_count_90d >= :min_complaints_90d)
ORDER BY r.action_priority_rank ASC
LIMIT :limit;
