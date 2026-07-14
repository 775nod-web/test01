// バックエンド(backend/models.py)のPydanticモデルに対応するAPI型定義。
// このデモアプリのAPI型はすべてこのファイルに集約する。

export type Scenario = "rules" | "hybrid";
export type Period = "7d" | "30d";
export type Channel = "all" | "mobile" | "debit";
export type ChannelLabel = "モバイル決済" | "デビットカード";
export type Priority = "最優先" | "高" | "中" | "低";
export type CaseStatus = "未着手" | "調査中" | "完了";
export type RecommendedAction = "承認" | "ステップアップ認証" | "保留" | "拒否";
export type InvestigationResult = "不正" | "正常" | "追加確認";
export type Contribution = "高" | "中" | "低";
export type KpiUnit = "count" | "jpy" | "percent" | "minutes";
export type RiskBand = "低" | "中" | "高";

export interface HealthResponse {
  status: "ok";
  service: string;
  note: string;
}

export interface KpiValue {
  key: string;
  label: string;
  value: number;
  unit: KpiUnit;
  description: string;
  previous_value: number;
  delta: number;
  is_primary: boolean;
}

export interface RateSeriesPoint {
  date: string;
  fraud_rate: number;
  normal_approval_rate: number;
}

export interface LossSeriesPoint {
  date: string;
  fraud_loss_amount: number;
  prevented_loss_amount: number;
}

export interface RiskDistributionBand {
  band: RiskBand;
  normal_count: number;
  fraud_count: number;
}

export interface ScenarioComparisonMetrics {
  fraud_capture_rate: number;
  normal_approval_rate: number;
  false_positive_rate: number;
  prevented_loss_amount: number;
  avg_investigation_time_minutes: number;
}

export interface ScenarioComparison {
  rules: ScenarioComparisonMetrics;
  hybrid: ScenarioComparisonMetrics;
  message: string;
}

export interface InvestigationQueueSummary {
  pending_count: number;
  in_progress_count: number;
  completed_count: number;
  by_priority: Record<Priority, number>;
}

export interface HighRiskTransactionRow {
  transaction_id: string;
  priority: Priority;
  risk_score: number;
  recommended_action: RecommendedAction;
  amount: number;
  merchant: string;
  transaction_datetime: string;
  status: CaseStatus;
}

export interface DashboardFilters {
  scenario: Scenario;
  period: Period;
  channel: Channel;
}

export interface DashboardResponse {
  filters: DashboardFilters;
  kpis: KpiValue[];
  comparison: ScenarioComparison;
  rate_series: RateSeriesPoint[];
  loss_series: LossSeriesPoint[];
  risk_distribution: RiskDistributionBand[];
  high_risk_transactions: HighRiskTransactionRow[];
  investigation_queue: InvestigationQueueSummary;
  data_updated_at: string;
}

export interface CaseSummary {
  transaction_id: string;
  risk_score: number;
  recommended_action: RecommendedAction;
  amount: number;
  transaction_datetime: string;
  merchant: string;
  detection_summary: string;
  related_transaction_count: number;
  priority: Priority;
  status: CaseStatus;
  channel: ChannelLabel;
  investigation_result: InvestigationResult | null;
}

export interface CaseListResponse {
  items: CaseSummary[];
  total: number;
}

export interface RiskFactor {
  name: string;
  observed_value: string;
  normal_value: string;
  contribution: Contribution;
  description: string;
}

export interface BehaviorComparisonRow {
  item: string;
  current_value: string;
  normal_value: string;
}

export interface TimelineEntry {
  time: string;
  merchant: string;
  amount: number;
  region: string;
  device: string;
  judgement: string;
  status: string;
}

export interface Last7DaysSummary {
  transaction_count: number;
  total_amount: number;
  average_amount: number;
  fraud_flagged_count: number;
}

export interface RelatedInfo {
  related_cards: string[];
  related_devices: string[];
  related_accounts: string[];
  related_merchants: string[];
}

export interface AiFactor {
  name: string;
  weight: number;
  description: string;
}

export interface AuditLogEntry {
  timestamp: string;
  actor: string;
  action: string;
}

export interface CaseDetail {
  transaction_id: string;
  risk_score: number;
  recommended_action: RecommendedAction;
  priority: Priority;
  status: CaseStatus;
  amount: number;
  transaction_datetime: string;
  merchant: string;
  customer_id: string;
  card_last4: string;
  region: string;
  channel: ChannelLabel;
  related_transaction_count: number;
  risk_factors: RiskFactor[];
  behavior_comparison: BehaviorComparisonRow[];
  timeline: TimelineEntry[];
  last_7_days_summary: Last7DaysSummary;
  related_info: RelatedInfo;
  rule_reasons: string[];
  ai_top_factors: AiFactor[];
  model_version: string;
  decision_datetime: string;
  data_updated_at: string;
  audit_log: AuditLogEntry[];
  investigation_result: InvestigationResult | null;
  investigation_memo: string | null;
  disclaimer: string;
}

export interface DecisionRequest {
  result: InvestigationResult;
  memo?: string;
}

export interface DecisionResponse {
  transaction_id: string;
  investigation_result: InvestigationResult;
  status: CaseStatus;
  memo: string | null;
  updated_at: string;
  toast_message: string;
  persistence_note: string;
}

export interface ApiErrorBody {
  detail: string;
}
