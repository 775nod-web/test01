-- Silver: contact_history
-- Sparse event log. De-dupes on contact_id, standardizes categorical
-- casing, validates referential integrity against silver.customers.
DROP TABLE IF EXISTS {silver}.contact_history;

CREATE TABLE {silver}.contact_history
USING DELTA
AS
SELECT
  contact_id,
  customer_id,
  contact_date,
  channel,
  reason,
  is_complaint,
  is_resolved,
  satisfaction_score
FROM (
  SELECT
    contact_id,
    customer_id,
    CAST(contact_date AS DATE) AS contact_date,
    INITCAP(TRIM(channel)) AS channel,
    INITCAP(TRIM(reason)) AS reason,
    CAST(COALESCE(is_complaint, 0) AS INT) AS is_complaint,
    CAST(COALESCE(is_resolved, 0) AS INT) AS is_resolved,
    CAST(satisfaction_score AS INT) AS satisfaction_score,
    ROW_NUMBER() OVER (PARTITION BY contact_id ORDER BY contact_date) AS rn
  FROM {bronze}.contact_history
  WHERE customer_id IN (SELECT customer_id FROM {silver}.customers)
) deduped
WHERE rn = 1;
