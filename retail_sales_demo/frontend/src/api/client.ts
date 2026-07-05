import type {
  ApiFilters,
  CategorySalesPoint,
  DailyStoreSalesPoint,
  KpiSummary,
  QuarantineReportItem,
  StoreRankingPoint,
} from '../types';

// All requests use relative "/api/..." paths: in dev, Vite's server.proxy
// (vite.config.ts) forwards them to the FastAPI dev server; in production
// the same FastAPI process serves both this SPA and /api/* from one origin
// (see docs/phase2_frontend.md), so no base URL or CORS setup is needed.

async function getJson<T>(path: string, params: Record<string, string | undefined>): Promise<T> {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) query.set(key, value);
  }
  const qs = query.toString();
  const res = await fetch(`${path}${qs ? `?${qs}` : ''}`);
  if (!res.ok) {
    throw new Error(`API request failed: ${path} (HTTP ${res.status})`);
  }
  return (await res.json()) as T;
}

function filterParams(filters: ApiFilters) {
  return {
    store_id: filters.storeId,
    date_from: filters.dateFrom,
    date_to: filters.dateTo,
  };
}

export function fetchKpiSummary(filters: ApiFilters): Promise<KpiSummary> {
  return getJson<KpiSummary>('/api/kpi-summary', filterParams(filters));
}

export function fetchDailyStoreSales(filters: ApiFilters): Promise<DailyStoreSalesPoint[]> {
  return getJson<DailyStoreSalesPoint[]>('/api/daily-store-sales', filterParams(filters));
}

export function fetchCategorySales(filters: ApiFilters): Promise<CategorySalesPoint[]> {
  return getJson<CategorySalesPoint[]>('/api/category-sales', filterParams(filters));
}

export function fetchStoreRanking(filters: ApiFilters): Promise<StoreRankingPoint[]> {
  return getJson<StoreRankingPoint[]>('/api/store-ranking', filterParams(filters));
}

export function fetchQuarantineReport(
  filters: ApiFilters & { issueType?: string },
): Promise<QuarantineReportItem[]> {
  return getJson<QuarantineReportItem[]>('/api/quarantine-report', {
    ...filterParams(filters),
    issue_type: filters.issueType,
  });
}
