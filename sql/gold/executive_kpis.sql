-- Gold: executive_kpis
-- One-row summary table for the Executive Overview page. Risk-distribution
-- and value-vs-risk-matrix breakdowns are built in Phase 5 as dashboard/
-- SQL assets (they are charts, not scalar KPIs) reading from
-- retention_action_list directly.
--
-- "Broad campaign audience" = every customer (today's blanket-campaign
-- approach). "Prioritized audience" = High-risk customers who are also
-- High or Medium value — the audience CLAUDE.md's storyline argues should
-- receive retention budget instead. estimated_value_at_risk_total is a
-- labeled SIMULATED figure (sum of the per-customer simulated proxy in
-- retention_action_list), not a real financial estimate.

DROP TABLE IF EXISTS {gold}.executive_kpis;

CREATE TABLE {gold}.executive_kpis
USING DELTA
AS
SELECT
  COUNT(*) AS total_customers,
  SUM(CASE WHEN risk_segment = 'High' THEN 1 ELSE 0 END) AS high_risk_customers,
  SUM(CASE WHEN risk_segment = 'Medium' THEN 1 ELSE 0 END) AS medium_risk_customers,
  SUM(CASE WHEN risk_segment = 'Low' THEN 1 ELSE 0 END) AS low_risk_customers,
  SUM(CASE WHEN risk_segment = 'High' AND value_segment = 'High' THEN 1 ELSE 0 END)
    AS high_risk_high_value_customers,
  SUM(CASE WHEN risk_segment = 'High' AND value_segment IN ('High', 'Medium') THEN 1 ELSE 0 END)
    AS prioritized_audience_count,
  COUNT(*) AS broad_campaign_audience_count,
  ROUND(SUM(estimated_value_at_risk), 2) AS estimated_value_at_risk_total_simulated,
  ROUND(
    SUM(CASE WHEN risk_segment = 'High' THEN estimated_value_at_risk ELSE 0 END), 2
  ) AS estimated_value_at_risk_high_risk_simulated
FROM {gold}.retention_action_list;
