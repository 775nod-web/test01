// Mirrors the Pydantic response models in
// retail_sales_demo/app/backend/main.py — keep the two in sync.

export interface KpiSummary {
  net_sales: number;
  gross_sales: number;
  gross_sales_is_estimated: boolean;
  gross_sales_note: string;
  transaction_count: number;
  units_sold: number;
  average_basket_size: number | null;
}

export interface DailyStoreSalesPoint {
  sales_date: string;
  store_id: string;
  store_name: string;
  net_sales: number;
  transaction_count: number;
  units_sold: number;
}

export interface CategorySalesPoint {
  category_id: string;
  category_name: string;
  net_sales: number;
  units_sold: number;
  share_of_net_sales: number | null;
}

export interface StoreRankingPoint {
  ranking_date: string;
  store_id: string;
  store_name: string;
  net_sales: number;
  rank: number;
}

export interface QuarantineReportItem {
  transaction_date: string;
  transaction_id: string;
  store_id: string | null;
  product_id: string | null;
  issue_type: string;
  net_sales: number | null;
  quantity: number | null;
  customer_id: string | null;
  customer_id_is_masked: boolean;
}

export interface MeResponse {
  user_email: string;
  /** null means "every store" (admin/HQ identity). */
  allowed_store_ids: string[] | null;
  roles: string[];
}

export interface AlertItem {
  alert_date: string;
  store_id: string;
  store_name: string;
  comparison_type: 'DoD' | 'WoW';
  current_value: number;
  previous_value: number;
  pct_change: number;
  threshold_pct: number;
}

export interface AuditLogEntry {
  logged_at: string;
  user_email: string;
  endpoint: string;
  store_id_filter: string | null;
  status_code: number;
}

export interface RequeueStatus {
  run_id: string | null;
  started_at: string | null;
  status: string | null;
  records_checked: number | null;
  reconciled_candidates_found: number | null;
}

export interface RequeueTriggerResult {
  triggered: boolean;
  run_id: string | null;
  message: string;
}

export interface ApiFilters {
  /** Comma-separated store IDs, matching the backend's `store_id` query param. */
  storeId?: string;
  dateFrom?: string;
  dateTo?: string;
  /**
   * Demo-only stand-in for a real logged-in identity: sent as the
   * `X-Forwarded-Email` header, which Databricks Apps is expected to set
   * from real SSO once deployed (unverified — see docs/phase3_governance_and_ops.md).
   * Omit to use the backend's DEMO_USER_EMAIL default (an admin identity).
   */
  asUser?: string;
}

export type Role = 'hq' | 'store' | 'product-planning' | 'data-quality';
