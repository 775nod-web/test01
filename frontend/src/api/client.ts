import type {
  CustomerDetailResponse,
  CustomerListResponse,
  HealthResponse,
  KpiResponse,
  PocSummaryResponse,
  RetentionActionListResponse,
  RiskDistributionItem,
  SegmentFilterOptions,
  TopDriverItem,
  ValueRiskMatrixItem,
} from "../types";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // ignore parse failure, keep statusText
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

function buildQuery(params: Record<string, string | number | undefined | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

export const api = {
  health: () => get<HealthResponse>("/api/health"),
  kpis: () => get<KpiResponse>("/api/kpis"),
  riskDistribution: () => get<RiskDistributionItem[]>("/api/risk-distribution"),
  valueRiskMatrix: () => get<ValueRiskMatrixItem[]>("/api/value-risk-matrix"),
  topRiskDrivers: () => get<TopDriverItem[]>("/api/top-risk-drivers"),
  segmentFilterOptions: () => get<SegmentFilterOptions>("/api/segments"),
  customers: (params: {
    risk_segment?: string;
    value_segment?: string;
    max_product_count?: number;
    balance_decline_pct?: number;
    card_spend_decline_pct?: number;
    app_decline_pct?: number;
    min_complaints_90d?: number;
    limit?: number;
  }) => get<CustomerListResponse>(`/api/customers${buildQuery(params)}`),
  customerDetail: (customerId: string) =>
    get<CustomerDetailResponse>(`/api/customers/${encodeURIComponent(customerId)}`),
  retentionActions: (params: {
    risk_segment?: string;
    value_segment?: string;
    limit?: number;
    offset?: number;
  }) => get<RetentionActionListResponse>(`/api/retention-actions${buildQuery(params)}`),
  retentionActionsExportUrl: (params: { risk_segment?: string; value_segment?: string }) =>
    `/api/retention-actions/export${buildQuery(params)}`,
  pocSummary: () => get<PocSummaryResponse>("/api/poc-summary"),
};
