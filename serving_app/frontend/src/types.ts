// backend/queries.py が返すJSONキー（Gold layerの列名）にそのまま合わせている。
// snake_case⇔camelCase変換を挟まないことで、バックエンドとの不一致バグを避ける。

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

export interface UnregisteredMasterReportRow {
  transaction_id: string;
  issue_type: string;
  store_id: string | null;
  is_store_registered: boolean;
  product_id: string | null;
  is_product_registered: boolean;
  customer_id: string | null;
  transaction_datetime: string | null;
  quantity: number | null;
  unit_price: number | null;
  discount_amount: number | null;
  sales_amount: number | null;
}
