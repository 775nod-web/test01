"""不正対策デモAPIのレスポンス/リクエストモデル定義。

すべて合成データ用のモデルであり、実データや個人情報は扱わない。
"""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

Scenario = Literal["rules", "hybrid"]
Period = Literal["7d", "30d"]
Channel = Literal["all", "mobile", "debit"]
ChannelLabel = Literal["モバイル決済", "デビットカード"]
Priority = Literal["最優先", "高", "中", "低"]
Status = Literal["未着手", "調査中", "完了"]
RecommendedAction = Literal["承認", "ステップアップ認証", "保留", "拒否"]
InvestigationResult = Literal["不正", "正常", "追加確認"]
Contribution = Literal["高", "中", "低"]
KpiUnit = Literal["count", "jpy", "percent", "minutes"]


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str = "fraud-decision-center"
    note: str = "本APIはデモ用の合成データのみを返します。"


# ─────────────────────────────
# 概況ダッシュボード
# ─────────────────────────────

class KpiValue(BaseModel):
    key: str
    label: str
    value: float
    unit: KpiUnit
    description: str
    previous_value: float
    delta: float
    is_primary: bool = False


class RateSeriesPoint(BaseModel):
    date: str
    fraud_rate: float
    normal_approval_rate: float


class LossSeriesPoint(BaseModel):
    date: str
    fraud_loss_amount: float
    prevented_loss_amount: float


class RiskDistributionBand(BaseModel):
    band: Literal["低", "中", "高"]
    normal_count: int
    fraud_count: int


class ScenarioComparisonMetrics(BaseModel):
    fraud_capture_rate: float
    normal_approval_rate: float
    false_positive_rate: float
    prevented_loss_amount: float
    avg_investigation_time_minutes: float


class ScenarioComparison(BaseModel):
    rules: ScenarioComparisonMetrics
    hybrid: ScenarioComparisonMetrics
    message: str


class InvestigationQueueSummary(BaseModel):
    pending_count: int
    in_progress_count: int
    completed_count: int
    by_priority: dict[Priority, int]


class HighRiskTransactionRow(BaseModel):
    transaction_id: str
    priority: Priority
    risk_score: float
    recommended_action: RecommendedAction
    amount: float
    merchant: str
    transaction_datetime: str
    status: Status


class DashboardFilters(BaseModel):
    scenario: Scenario
    period: Period
    channel: Channel


class DashboardResponse(BaseModel):
    filters: DashboardFilters
    kpis: List[KpiValue]
    comparison: ScenarioComparison
    rate_series: List[RateSeriesPoint]
    loss_series: List[LossSeriesPoint]
    risk_distribution: List[RiskDistributionBand]
    high_risk_transactions: List[HighRiskTransactionRow]
    investigation_queue: InvestigationQueueSummary
    data_updated_at: str


# ─────────────────────────────
# 調査ケース一覧・詳細
# ─────────────────────────────

class CaseSummary(BaseModel):
    transaction_id: str
    risk_score: float
    recommended_action: RecommendedAction
    amount: float
    transaction_datetime: str
    merchant: str
    detection_summary: str
    related_transaction_count: int
    priority: Priority
    status: Status
    channel: ChannelLabel
    investigation_result: Optional[InvestigationResult] = None


class CaseListResponse(BaseModel):
    items: List[CaseSummary]
    total: int


class RiskFactor(BaseModel):
    name: str
    observed_value: str
    normal_value: str
    contribution: Contribution
    description: str


class BehaviorComparisonRow(BaseModel):
    item: str
    current_value: str
    normal_value: str


class TimelineEntry(BaseModel):
    time: str
    merchant: str
    amount: float
    region: str
    device: str
    judgement: str
    status: str


class Last7DaysSummary(BaseModel):
    transaction_count: int
    total_amount: float
    average_amount: float
    fraud_flagged_count: int


class RelatedInfo(BaseModel):
    related_cards: List[str]
    related_devices: List[str]
    related_accounts: List[str]
    related_merchants: List[str]


class AiFactor(BaseModel):
    name: str
    weight: float
    description: str


class AuditLogEntry(BaseModel):
    timestamp: str
    actor: str
    action: str


class CaseDetail(BaseModel):
    transaction_id: str
    risk_score: float
    recommended_action: RecommendedAction
    priority: Priority
    status: Status
    amount: float
    transaction_datetime: str
    merchant: str
    customer_id: str
    card_last4: str
    region: str
    channel: ChannelLabel
    related_transaction_count: int
    risk_factors: List[RiskFactor]
    behavior_comparison: List[BehaviorComparisonRow]
    timeline: List[TimelineEntry]
    last_7_days_summary: Last7DaysSummary
    related_info: RelatedInfo
    rule_reasons: List[str]
    ai_top_factors: List[AiFactor]
    model_version: str
    decision_datetime: str
    data_updated_at: str
    audit_log: List[AuditLogEntry]
    investigation_result: Optional[InvestigationResult] = None
    investigation_memo: Optional[str] = None
    disclaimer: str = (
        "リスクスコアは不正を確定するものではありません。"
        "複数のリスク要因を調査判断の補助として提示しています。"
    )


class DecisionRequest(BaseModel):
    result: InvestigationResult
    memo: Optional[str] = Field(default=None, max_length=500)


class DecisionResponse(BaseModel):
    transaction_id: str
    investigation_result: InvestigationResult
    status: Status
    memo: Optional[str] = None
    updated_at: str
    toast_message: str = "調査結果を登録しました。"
    persistence_note: str = (
        "この結果はセッション内のみ保持され、モデル改善へのフィードバックを模したものです。"
    )
