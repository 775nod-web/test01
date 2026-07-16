import type { HealthResponse, MetadataResponse } from "../types";

// Python APIとは同一オリジンの相対パスで通信する（Databricks Apps上でも同様）。
const API_BASE = "/api";

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    throw new Error(`APIエラー: ${path} (status ${response.status})`);
  }
  return (await response.json()) as T;
}

export function fetchHealth(): Promise<HealthResponse> {
  return getJson<HealthResponse>("/health");
}

export function fetchMetadata(): Promise<MetadataResponse> {
  return getJson<MetadataResponse>("/metadata");
}
