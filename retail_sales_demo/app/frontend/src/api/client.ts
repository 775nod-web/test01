import type {
  AlertRow,
  CategorySales,
  DailyStoreSales,
  KpiSummary,
  QuarantineReportRow,
  QuarantineSummaryRow,
  StoreRanking,
} from "../types";

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) {
    throw new Error(`API request failed: ${path} (${res.status})`);
  }
  return res.json() as Promise<T>;
}

export function fetchKpiSummary(storeId?: string): Promise<KpiSummary> {
  const qs = storeId ? `?store_id=${encodeURIComponent(storeId)}` : "";
  return getJson<KpiSummary>(`/api/kpi-summary${qs}`);
}

export function fetchDailyStoreSales(storeId?: string): Promise<DailyStoreSales[]> {
  const qs = storeId ? `?store_id=${encodeURIComponent(storeId)}` : "";
  return getJson<DailyStoreSales[]>(`/api/daily-store-sales${qs}`);
}

export function fetchCategorySales(): Promise<CategorySales[]> {
  return getJson<CategorySales[]>("/api/category-sales");
}

export function fetchStoreRanking(limit = 20): Promise<StoreRanking[]> {
  return getJson<StoreRanking[]>(`/api/store-ranking?limit=${limit}`);
}

export function fetchQuarantineReport(issueType?: string): Promise<QuarantineReportRow[]> {
  const qs = issueType ? `?issue_type=${encodeURIComponent(issueType)}` : "";
  return getJson<QuarantineReportRow[]>(`/api/quarantine-report${qs}`);
}

export function fetchQuarantineSummary(): Promise<QuarantineSummaryRow[]> {
  return getJson<QuarantineSummaryRow[]>("/api/quarantine-summary");
}

export function fetchAlerts(): Promise<AlertRow[]> {
  return getJson<AlertRow[]>("/api/alerts");
}

export async function triggerReconciliation(): Promise<{ triggered: boolean; reason?: string; run_id?: number }> {
  const res = await fetch("/api/reconcile-quarantine", { method: "POST" });
  return res.json();
}
