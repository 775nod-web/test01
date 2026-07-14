-- Silver: app_activity
-- One row per (customer_id, activity_month).
DROP TABLE IF EXISTS {silver}.app_activity;

CREATE TABLE {silver}.app_activity
USING DELTA
AS
SELECT
  customer_id,
  activity_month,
  login_count,
  session_count,
  avg_session_minutes,
  days_since_last_login_eom
FROM (
  SELECT
    customer_id,
    CAST(activity_month AS DATE) AS activity_month,
    CAST(COALESCE(login_count, 0) AS INT) AS login_count,
    CAST(COALESCE(session_count, 0) AS INT) AS session_count,
    CAST(COALESCE(avg_session_minutes, 0) AS DOUBLE) AS avg_session_minutes,
    CAST(COALESCE(days_since_last_login_eom, 999) AS INT) AS days_since_last_login_eom,
    ROW_NUMBER() OVER (
      PARTITION BY customer_id, activity_month ORDER BY login_count DESC
    ) AS rn
  FROM {bronze}.app_activity
  WHERE customer_id IN (SELECT customer_id FROM {silver}.customers)
) deduped
WHERE rn = 1;
