import type {
  CustomerDetailResponse,
  CustomersListResponse,
  HealthResponse,
  MetadataResponse,
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
