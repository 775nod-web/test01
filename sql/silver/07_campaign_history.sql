-- Silver: campaign_history
-- Sparse event log. De-dupes on campaign_id, standardizes categorical
-- casing, validates referential integrity against silver.customers.
DROP TABLE IF EXISTS {silver}.campaign_history;

CREATE TABLE {silver}.campaign_history
USING DELTA
AS
SELECT
  campaign_id,
  customer_id,
  campaign_date,
  campaign_type,
  channel,
  responded_flag,
  converted_flag
FROM (
  SELECT
    campaign_id,
    customer_id,
    CAST(campaign_date AS DATE) AS campaign_date,
    INITCAP(TRIM(campaign_type)) AS campaign_type,
    INITCAP(TRIM(channel)) AS channel,
    CAST(COALESCE(responded_flag, 0) AS INT) AS responded_flag,
    CAST(COALESCE(converted_flag, 0) AS INT) AS converted_flag,
    ROW_NUMBER() OVER (PARTITION BY campaign_id ORDER BY campaign_date) AS rn
  FROM {bronze}.campaign_history
  WHERE customer_id IN (SELECT customer_id FROM {silver}.customers)
) deduped
WHERE rn = 1;
