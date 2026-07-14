-- Customer 360 page — contact and complaint history
-- Business question: What has this customer told us directly, and have we
-- resolved it?
-- Params: :customer_id (text, required)
SELECT
  contact_date,
  channel,
  reason,
  is_complaint,
  is_resolved,
  satisfaction_score
FROM {silver}.contact_history
WHERE customer_id = :customer_id
ORDER BY contact_date DESC;
