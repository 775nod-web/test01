-- Silver: product_holdings
-- One row per (customer_id, activity_month).
DROP TABLE IF EXISTS {silver}.product_holdings;

CREATE TABLE {silver}.product_holdings
USING DELTA
AS
SELECT
  customer_id,
  activity_month,
  product_count,
  has_checking,
  has_savings,
  has_credit_card,
  has_loan,
  has_investment
FROM (
  SELECT
    customer_id,
    CAST(activity_month AS DATE) AS activity_month,
    CAST(product_count AS INT) AS product_count,
    CAST(COALESCE(has_checking, 0) AS INT) AS has_checking,
    CAST(COALESCE(has_savings, 0) AS INT) AS has_savings,
    CAST(COALESCE(has_credit_card, 0) AS INT) AS has_credit_card,
    CAST(COALESCE(has_loan, 0) AS INT) AS has_loan,
    CAST(COALESCE(has_investment, 0) AS INT) AS has_investment,
    ROW_NUMBER() OVER (
      PARTITION BY customer_id, activity_month ORDER BY product_count DESC
    ) AS rn
  FROM {bronze}.product_holdings
  WHERE customer_id IN (SELECT customer_id FROM {silver}.customers)
) deduped
WHERE rn = 1;
