export type DataMode = "demo" | "databricks";

export interface HealthResponse {
  status: string;
}

export interface MetadataResponse {
  app_name: string;
  api_version: string;
  data_mode: DataMode;
  updated_at: string;
}
