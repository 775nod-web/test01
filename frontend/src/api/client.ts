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

const NETWORK_ERROR_MESSAGE = "サーバーに接続できませんでした。しばらくしてから再度お試しください。";
const UNEXPECTED_ERROR_MESSAGE = "予期しないエラーが発生しました。しばらくしてから再度お試しください。";

async function extractErrorDetail(response: Response, path: string): Promise<string> {
  const detail = await response
    .json()
    .then((body: { detail?: string }) => body.detail)
    .catch(() => undefined);
  return detail ?? `APIエラー: ${path} (status ${response.status})`;
}

async function getJson<T>(path: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`);
  } catch {
    throw new Error(NETWORK_ERROR_MESSAGE);
  }

  if (!response.ok) {
    throw new Error(await extractErrorDetail(response, path));
  }

  try {
    return (await response.json()) as T;
  } catch {
    throw new Error(UNEXPECTED_ERROR_MESSAGE);
  }
}

async function postJson<TResponse, TBody>(path: string, body: TBody): Promise<TResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new Error(NETWORK_ERROR_MESSAGE);
  }

  if (!response.ok) {
    throw new Error(await extractErrorDetail(response, path));
  }

  try {
    return (await response.json()) as TResponse;
  } catch {
    throw new Error(UNEXPECTED_ERROR_MESSAGE);
  }
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
