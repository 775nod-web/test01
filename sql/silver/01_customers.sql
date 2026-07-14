-- Silver: customers
-- Enforces types, standardizes categorical casing, validates customer_id
-- format, and de-duplicates defensively (Bronze is synthetic and already
-- unique, but a real source system would not guarantee that, so the same
-- de-dup pattern used here would apply unchanged to real data).
DROP TABLE IF EXISTS {silver}.customers;

CREATE TABLE {silver}.customers
USING DELTA
AS
SELECT
  customer_id,
  CAST(signup_date AS DATE) AS signup_date,
  CAST(tenure_months AS INT) AS tenure_months,
  TRIM(age_band) AS age_band,
  INITCAP(TRIM(acquisition_channel)) AS acquisition_channel,
  INITCAP(TRIM(home_region)) AS home_region,
  INITCAP(TRIM(customer_value_segment)) AS customer_value_segment,
  CAST(simulated_annual_value AS DOUBLE) AS simulated_annual_value,
  CAST(churn_label_90d AS INT) AS churn_label_90d,
  CASE
    WHEN customer_id RLIKE '^CUST[0-9]{6}$' THEN 'valid'
    ELSE 'invalid_customer_id'
  END AS data_quality_status
FROM (
  SELECT *,
    ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY signup_date) AS rn
  FROM {bronze}.customers
) deduped
WHERE rn = 1;
