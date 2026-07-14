-- Executive Overview page — top-line KPIs
-- Business question: Where should we focus limited retention budget?
-- Params: none. Reads the single pre-aggregated row built in Phase 4.
SELECT
  total_customers,
  high_risk_customers,
  medium_risk_customers,
  low_risk_customers,
  high_risk_high_value_customers,
  prioritized_audience_count,
  broad_campaign_audience_count,
  estimated_value_at_risk_total_simulated,
  estimated_value_at_risk_high_risk_simulated
FROM {gold}.executive_kpis;
