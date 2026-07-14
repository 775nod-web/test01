-- Silver: account_transactions
-- One row per (customer_id, activity_month). De-dupes, casts types,
-- coalesces nullable numeric fields to 0, and drops rows referencing a
-- customer_id not present in silver.customers (referential integrity).
DROP TABLE IF EXISTS {silver}.account_transactions;

CREATE TABLE {silver}.account_transactions
USING DELTA
AS
SELECT
  customer_id,
  activity_month,
  avg_daily_balance,
  eom_balance,
  deposit_count,
  withdrawal_count,
  transfer_out_amount,
  salary_deposit_flag,
  total_transaction_amount
FROM (
  SELECT
    customer_id,
    CAST(activity_month AS DATE) AS activity_month,
    CAST(avg_daily_balance AS DOUBLE) AS avg_daily_balance,
    CAST(eom_balance AS DOUBLE) AS eom_balance,
    CAST(COALESCE(deposit_count, 0) AS INT) AS deposit_count,
    CAST(COALESCE(withdrawal_count, 0) AS INT) AS withdrawal_count,
    CAST(COALESCE(transfer_out_amount, 0) AS DOUBLE) AS transfer_out_amount,
    CAST(COALESCE(salary_deposit_flag, 0) AS INT) AS salary_deposit_flag,
    CAST(total_transaction_amount AS DOUBLE) AS total_transaction_amount,
    ROW_NUMBER() OVER (
      PARTITION BY customer_id, activity_month ORDER BY eom_balance DESC
    ) AS rn
  FROM {bronze}.account_transactions
  WHERE customer_id IN (SELECT customer_id FROM {silver}.customers)
) deduped
WHERE rn = 1;
