import type {
  CustomerDetailResponse,
  CustomersListResponse,
  DecisionRecord,
  DecisionRequest,
  FeedbackSummaryResponse,
  HealthResponse,
  MetadataResponse,
  RecommendationResponse,
} from "../types";

// Python APIとは同一オリジンの相対パスで通信する（Databricks Apps上でも同様）。
const API_BASE = "/api";

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    const detail = await response
      .json()
      .then((body: { detail?: string }) => body.detail)
      .catch(() => undefined);
    throw new Error(detail ?? `APIエラー: ${path} (status ${response.status})`);
  }
  return (await response.json()) as T;
}

async function postJson<TResponse, TBody>(path: string, body: TBody): Promise<TResponse> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const detail = await response
      .json()
      .then((responseBody: { detail?: string }) => responseBody.detail)
      .catch(() => undefined);
    throw new Error(detail ?? `APIエラー: ${path} (status ${response.status})`);
  }
  return (await response.json()) as TResponse;
}

export function fetchHealth(): Promise<HealthResponse> {
  return getJson<HealthResponse>("/health");
}

export function fetchMetadata(): Promise<MetadataResponse> {
  return getJson<MetadataResponse>("/metadata");
}

export function fetchCustomers(): Promise<CustomersListResponse> {
  return getJson<CustomersListResponse>("/customers");
}

export function fetchCustomerDetail(customerId: string): Promise<CustomerDetailResponse> {
  return getJson<CustomerDetailResponse>(`/customers/${encodeURIComponent(customerId)}`);
}

export function fetchRecommendation(customerId: string): Promise<RecommendationResponse> {
  return getJson<RecommendationResponse>(
    `/customers/${encodeURIComponent(customerId)}/recommendation`,
  );
}

export function postDecision(
  customerId: string,
  body: DecisionRequest,
): Promise<DecisionRecord> {
  return postJson<DecisionRecord, DecisionRequest>(
    `/customers/${encodeURIComponent(customerId)}/decision`,
    body,
  );
}

export function fetchFeedbackSummary(): Promise<FeedbackSummaryResponse> {
  return getJson<FeedbackSummaryResponse>("/feedback-summary");
}
