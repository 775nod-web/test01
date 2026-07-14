// Mirrors backend/schemas.py — keep field names identical to the API.

export type RiskSegment = "High" | "Medium" | "Low";
export type ValueSegment = "High" | "Medium" | "Low";

export interface HealthResponse {
  status: "ok" | "error";
  data_mode: "databricks" | "local";
  detail: string | null;
}

export interface KpiResponse {
  total_customers: number;
  high_risk_customers: number;
  medium_risk_customers: number;
  low_risk_customers: number;
  high_risk_high_value_customers: number;
  prioritized_audience_count: number;
  broad_campaign_audience_count: number;
  estimated_value_at_risk_total_simulated: number;
  estimated_value_at_risk_high_risk_simulated: number;
}

export interface RiskDistributionItem {
  risk_segment: RiskSegment;
  customer_count: number;
  avg_risk_score: number;
}

export interface ValueRiskMatrixItem {
  value_segment: ValueSegment;
  risk_segment: RiskSegment;
  customer_count: number;
  estimated_value_at_risk_simulated: number;
}

export interface TopDriverItem {
  primary_driver: string;
  customer_count: number;
  estimated_value_at_risk_simulated: number;
}

export interface SegmentFilterOptions {
  risk_segments: string[];
  value_segments: string[];
}

export interface CustomerListItem {
  customer_id: string;
  value_segment: ValueSegment;
  risk_segment: RiskSegment;
  risk_score: number;
  primary_driver: string;
  product_count: number;
  balance_change_90d_pct: number | null;
  card_spend_change_90d_pct: number | null;
  login_change_90d_pct: number | null;
  complaint_count_90d: number;
  unresolved_contacts_total: number;
  recommended_action: string;
  recommended_channel: string;
}

export interface CustomerListResponse {
  items: CustomerListItem[];
  count: number;
}

export interface CustomerTrendPoint {
  activity_month: string;
  eom_balance: number;
  avg_daily_balance: number;
  salary_deposit_flag: number;
  card_spend_amount: number;
  card_txn_count: number;
  declined_txn_count: number;
  login_count: number;
  session_count: number;
  days_since_last_login_eom: number;
  product_count: number;
}

export interface ContactHistoryItem {
  contact_date: string;
  channel: string;
  reason: string;
  is_complaint: number;
  is_resolved: number;
  satisfaction_score: number;
}

export interface CustomerDetailResponse {
  customer_id: string;
  signup_date: string;
  tenure_months: number;
  age_band: string;
  acquisition_channel: string;
  home_region: string;
  value_segment: ValueSegment;
  simulated_annual_value: number;
  current_balance: number;
  avg_balance_90d: number | null;
  balance_change_30d_pct: number | null;
  balance_change_90d_pct: number | null;
  transfer_out_amount_90d: number | null;
  salary_deposit_active: number;
  salary_deposit_stopped_flag: number;
  product_count: number;
  product_count_90d_ago: number | null;
  card_spend_90d: number | null;
  card_spend_change_30d_pct: number | null;
  card_spend_change_90d_pct: number | null;
  declined_txn_count_90d: number | null;
  days_since_last_login: number;
  login_count_90d: number | null;
  login_change_30d_pct: number | null;
  login_change_90d_pct: number | null;
  app_engagement_score: number | null;
  contact_count_90d: number;
  complaint_count_90d: number;
  unresolved_contacts_total: number;
  avg_satisfaction_score_90d: number | null;
  campaign_count_12m: number;
  campaign_response_rate_12m: number;
  campaign_conversion_rate_12m: number;
  risk_score: number;
  risk_segment: RiskSegment;
  primary_driver: string;
  secondary_driver: string;
  recommended_action: string;
  recommended_channel: string;
  human_review_required: number;
  estimated_value_at_risk: number;
  trends: CustomerTrendPoint[];
  contact_history: ContactHistoryItem[];
}

export interface RetentionActionItem {
  customer_id: string;
  value_segment: ValueSegment;
  risk_segment: RiskSegment;
  risk_score: number;
  primary_driver: string;
  secondary_driver: string;
  recommended_action: string;
  recommended_channel: string;
  human_review_required: number;
  estimated_value_at_risk: number;
  action_priority_rank: number;
}

export interface RetentionActionListResponse {
  items: RetentionActionItem[];
  limit: number;
  offset: number;
}

export interface CrossSellCandidate {
  customer_id: string;
  value_segment: ValueSegment;
  product_count: number;
  app_engagement_score: number | null;
  complaint_count_90d: number;
  risk_segment: RiskSegment;
}

export interface PocSummaryResponse {
  synthetic_elements: string[];
  must_validate_with_bank_data: string[];
  poc_success_metrics: string[];
  free_edition_limitations: string[];
  cross_sell_reuse_note: string;
  cross_sell_sample: CrossSellCandidate[];
}
