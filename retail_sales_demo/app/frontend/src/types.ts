export interface KpiSummary {
  net_sales: number;
  gross_sales: number;
  gross_sales_is_estimated: boolean;
  transaction_count: number;
  units_sold: number;
  average_basket_size: number;
}

export interface DailyStoreSales {
  sales_date: string;
  store_id: string;
  store_name: string;
  region: string;
  transaction_count: number;
  total_quantity: number;
  total_sales_amount: number;
}

export interface CategorySales {
  category: string;
  product_count: number;
  transaction_count: number;
  total_quantity: number;
  total_sales_amount: number;
}

export interface StoreRanking {
  sales_rank: number;
  store_id: string;
  store_name: string;
  region: string;
  store_type: string;
  total_sales_amount: number;
  total_quantity: number;
  transaction_count: number;
}

export interface QuarantineReportRow {
  transaction_id: string;
  issue_type: string;
  store_id: string | null;
  product_id: string | null;
  customer_id: string | null;
  transaction_datetime: string | null;
  is_store_registered: boolean;
  is_product_registered: boolean;
  quantity: number | null;
  unit_price: number | null;
  discount_amount: number | null;
  sales_amount: number | null;
}

export interface QuarantineSummaryRow {
  report_date: string;
  issue_type: string;
  unregistered_count: number;
}

export interface AlertRow {
  alert_date: string;
  store_id: string;
  store_name: string;
  sales_change_pct: number;
  threshold_pct: number;
  message: string;
}

export type Role = "hq" | "store_manager" | "merchandising" | "data_quality";
