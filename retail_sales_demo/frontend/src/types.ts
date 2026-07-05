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
}

export interface ApiFilters {
  /** Comma-separated store IDs, matching the backend's `store_id` query param. */
  storeId?: string;
  dateFrom?: string;
  dateTo?: string;
}

export type Role = 'hq' | 'store' | 'product-planning' | 'data-quality';
