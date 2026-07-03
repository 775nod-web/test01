// backend/models.py と1対1で対応する型定義。

export interface DailyKpi {
  kpi_date: string;
  dau: number;
  new_signup_count: number;
  total_paid_users: number;
  total_free_users: number;
  daily_revenue: number;
  upgrade_click_count: number;
  cancel_click_count: number;
  new_paid_conversion_count: number;
  churn_count: number;
  free_to_paid_rate: number | null;
}

export interface SalesPerPlan {
  sales_month: string;
  plan_type: string;
  total_revenue: number;
  transaction_count: number;
  success_count: number;
  failed_count: number;
  avg_transaction_amount: number | null;
  new_subscriber_count: number;
  churned_subscriber_count: number;
  active_subscriber_count: number;
  failed_payment_rate: number | null;
  revenue_mom_change_rate: number | null;
}

export interface FailedPaymentUser {
  user_id: string;
  plan_type: string | null;
  country_code: string | null;
  user_segment: string | null;
  is_active: boolean | null;
  total_failed_count: number;
  total_success_count: number;
  latest_payment_date: string | null;
  latest_payment_status: string | null;
  latest_amount: number | null;
  has_recent_cancel_click: boolean;
  churn_risk_flag: boolean;
}

export interface DataQualitySummary {
  run_date: string;
  source_table: string;
  dq_check_name: string;
  issue_count: number;
  total_records: number;
  description: string | null;
  issue_rate: number | null;
}
