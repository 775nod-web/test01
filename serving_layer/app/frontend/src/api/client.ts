import type { DailyKpi, DataQualitySummary, FailedPaymentUser, SalesPerPlan } from "./types";

const BASE_URL = "/api/v1";

async function getJson<T>(path: string, params?: Record<string, string | number | undefined>): Promise<T> {
  const query = params
    ? "?" +
      Object.entries(params)
        .filter(([, v]) => v !== undefined)
        .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
        .join("&")
    : "";
  const res = await fetch(`${BASE_URL}${path}${query}`);
  if (!res.ok) {
    throw new Error(`API request failed: ${path} (${res.status})`);
  }
  return (await res.json()) as T;
}

export const api = {
  getDailyKpi: (days = 30) =>
    getJson<DailyKpi[]>("/daily-kpi", { days }),

  getSalesPerPlan: (months = 12) =>
    getJson<SalesPerPlan[]>("/sales-per-plan", { months }),

  getFailedPaymentUsers: (risk: "all" | "high" | "low" = "all", planType?: string, userSegment?: string) =>
    getJson<FailedPaymentUser[]>("/failed-payment-users", {
      risk,
      plan_type: planType,
      user_segment: userSegment,
    }),

  getDataQualitySummary: (days = 14) =>
    getJson<DataQualitySummary[]>("/data-quality-summary", { days }),
};
