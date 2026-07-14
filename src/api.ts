import type {
  ApiErrorBody,
  CaseDetail,
  CaseListResponse,
  Channel,
  DashboardResponse,
  DecisionRequest,
  DecisionResponse,
  HealthResponse,
  Period,
  Scenario,
} from "./types";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });

  if (!response.ok) {
    let message = `リクエストに失敗しました(HTTP ${response.status})。`;
    try {
      const body = (await response.json()) as ApiErrorBody;
      if (body.detail) {
        message = body.detail;
      }
    } catch {
      // レスポンスボディがJSONでない場合は既定メッセージを使用する
    }
    throw new ApiError(response.status, message);
  }

  return (await response.json()) as T;
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/api/health");
}

export interface DashboardParams {
  scenario: Scenario;
  period: Period;
  channel: Channel;
}

export function getDashboard(params: DashboardParams): Promise<DashboardResponse> {
  const query = new URLSearchParams({
    scenario: params.scenario,
    period: params.period,
    channel: params.channel,
  });
  return request<DashboardResponse>(`/api/dashboard?${query.toString()}`);
}

export function getCases(): Promise<CaseListResponse> {
  return request<CaseListResponse>("/api/cases");
}

export function getCaseDetail(transactionId: string): Promise<CaseDetail> {
  return request<CaseDetail>(`/api/cases/${encodeURIComponent(transactionId)}`);
}

export function postCaseDecision(
  transactionId: string,
  body: DecisionRequest,
): Promise<DecisionResponse> {
  return request<DecisionResponse>(`/api/cases/${encodeURIComponent(transactionId)}/decision`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}
