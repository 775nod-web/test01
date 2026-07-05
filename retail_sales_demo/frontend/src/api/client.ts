import type {
  AlertItem,
  ApiFilters,
  AuditLogEntry,
  CategorySalesPoint,
  DailyStoreSalesPoint,
  KpiSummary,
  MeResponse,
  QuarantineReportItem,
  RequeueStatus,
  RequeueTriggerResult,
  StoreRankingPoint,
} from '../types';

// All requests use relative "/api/..." paths: in dev, Vite's server.proxy
// (vite.config.ts) forwards them to the FastAPI dev server; in production
// the same FastAPI process serves both this SPA and /api/* from one origin
// (see docs/phase2_frontend.md), so no base URL or CORS setup is needed.

async function request<T>(
  method: 'GET' | 'POST',
  path: string,
  params: Record<string, string | undefined>,
  asUser?: string,
): Promise<T> {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) query.set(key, value);
  }
  const qs = query.toString();
  const headers: Record<string, string> = {};
  // Demo-only: stands in for the identity Databricks Apps would forward
  // from real SSO (X-Forwarded-Email) — see ApiFilters.asUser in types.ts.
  if (asUser) headers['X-Forwarded-Email'] = asUser;

  const res = await fetch(`${path}${qs ? `?${qs}` : ''}`, { method, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const detail = body?.detail ? `: ${body.detail}` : '';
    throw new Error(`API request failed: ${path} (HTTP ${res.status})${detail}`);
  }
  return (await res.json()) as T;
}

function getJson<T>(path: string, params: Record<string, string | undefined>, asUser?: string): Promise<T> {
  return request<T>('GET', path, params, asUser);
}

function filterParams(filters: ApiFilters) {
  return {
    store_id: filters.storeId,
    date_from: filters.dateFrom,
    date_to: filters.dateTo,
  };
}

export function fetchMe(asUser?: string): Promise<MeResponse> {
  return getJson<MeResponse>('/api/me', {}, asUser);
}

export function fetchKpiSummary(filters: ApiFilters): Promise<KpiSummary> {
  return getJson<KpiSummary>('/api/kpi-summary', filterParams(filters), filters.asUser);
}

export function fetchDailyStoreSales(filters: ApiFilters): Promise<DailyStoreSalesPoint[]> {
  return getJson<DailyStoreSalesPoint[]>('/api/daily-store-sales', filterParams(filters), filters.asUser);
}

export function fetchCategorySales(filters: ApiFilters): Promise<CategorySalesPoint[]> {
  return getJson<CategorySalesPoint[]>('/api/category-sales', filterParams(filters), filters.asUser);
}

export function fetchStoreRanking(filters: ApiFilters): Promise<StoreRankingPoint[]> {
  return getJson<StoreRankingPoint[]>('/api/store-ranking', filterParams(filters), filters.asUser);
}

export function fetchQuarantineReport(
  filters: ApiFilters & { issueType?: string },
): Promise<QuarantineReportItem[]> {
  return getJson<QuarantineReportItem[]>(
    '/api/quarantine-report',
    { ...filterParams(filters), issue_type: filters.issueType },
    filters.asUser,
  );
}

export function fetchAlerts(filters: ApiFilters = {}): Promise<AlertItem[]> {
  return getJson<AlertItem[]>('/api/alerts', filterParams(filters), filters.asUser);
}

export function fetchAuditLog(limit = 200, asUser?: string): Promise<AuditLogEntry[]> {
  return getJson<AuditLogEntry[]>('/api/audit-log', { limit: String(limit) }, asUser);
}

export function fetchRequeueStatus(): Promise<RequeueStatus> {
  return getJson<RequeueStatus>('/api/requeue-status', {});
}

export function triggerRequeueJob(): Promise<RequeueTriggerResult> {
  return request<RequeueTriggerResult>('POST', '/api/requeue-trigger', {});
}
