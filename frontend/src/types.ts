export type DataMode = "demo" | "databricks";
export type ModelMode = "trained" | "precomputed";
export type RiskBand = "high" | "medium" | "low";

export interface HealthResponse {
  status: string;
}

export interface MetadataResponse {
  app_name: string;
  api_version: string;
  data_mode: DataMode;
  updated_at: string;
  model_mode?: ModelMode;
  customer_count?: number;
}

export interface CustomerSummary {
  customer_id: string;
  display_name: string;
  risk_band: RiskBand;
  risk_band_label: string;
  churn_probability: number;
  service_count: number;
  previous_service_count: number;
  top_reason: string | null;
}

export interface CustomersListResponse {
  data_mode: DataMode;
  model_mode: ModelMode;
  updated_at: string;
  customers: CustomerSummary[];
}

export interface ServiceUsage {
  monthly_amount: number[];
  monthly_frequency: number[];
  last_used_date: string | null;
  days_since_last_used: number | null;
  period_change_pct: number | null;
}

export interface CampaignRecord {
  sent_date: string;
  campaign_type: string;
  response: string;
  cost: number;
}

export interface SupportSummary {
  inquiry_count: number;
  last_inquiry_date: string | null;
  recent_categories: string[];
}

export interface CustomerDetail {
  customer_id: string;
  display_name: string;
  signup_date: string;
  services: Record<string, ServiceUsage>;
  service_count: number;
  previous_service_count: number;
  combined_qr_card: ServiceUsage;
  campaigns: CampaignRecord[];
  support_summary: SupportSummary;
  data_sources: string[];
}

export interface Prediction {
  churn_probability: number;
  risk_band: RiskBand;
  risk_band_label: string;
  reasons: string[];
  model_version: string;
  inference_at: string;
}

export interface CustomerDetailResponse {
  data_mode: DataMode;
  model_mode: ModelMode;
  updated_at: string;
  customer: CustomerDetail;
  prediction: Prediction;
}
