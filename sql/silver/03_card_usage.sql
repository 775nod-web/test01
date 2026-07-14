-- Silver: card_usage
-- One row per (customer_id, activity_month).
DROP TABLE IF EXISTS {silver}.card_usage;

CREATE TABLE {silver}.card_usage
USING DELTA
AS
SELECT
  customer_id,
  activity_month,
  card_spend_amount,
  card_txn_count,
  declined_txn_count,
  card_active_flag
FROM (
  SELECT
    customer_id,
    CAST(activity_month AS DATE) AS activity_month,
    CAST(COALESCE(card_spend_amount, 0) AS DOUBLE) AS card_spend_amount,
    CAST(COALESCE(card_txn_count, 0) AS INT) AS card_txn_count,
    CAST(COALESCE(declined_txn_count, 0) AS INT) AS declined_txn_count,
    CAST(COALESCE(card_active_flag, 0) AS INT) AS card_active_flag,
    ROW_NUMBER() OVER (
      PARTITION BY customer_id, activity_month ORDER BY card_spend_amount DESC
    ) AS rn
  FROM {bronze}.card_usage
  WHERE customer_id IN (SELECT customer_id FROM {silver}.customers)
) deduped
WHERE rn = 1;
