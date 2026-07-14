"""
Typed response models for every /api/* endpoint. Field names match the
underlying SQL column names in sql/queries/*.sql so the mapping from query
result to API response is a straight pass-through (see backend/services/).
"""

from __future__ import annotations

import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

RiskSegment = Literal["High", "Medium", "Low"]
ValueSegment = Literal["High", "Medium", "Low"]


class HealthResponse(BaseModel):
    status: Literal["ok", "error"]
    data_mode: Literal["databricks", "local"]
    detail: Optional[str] = None


class KpiResponse(BaseModel):
    total_customers: int
    high_risk_customers: int
    medium_risk_customers: int
    low_risk_customers: int
    high_risk_high_value_customers: int
    prioritized_audience_count: int
    broad_campaign_audience_count: int
    estimated_value_at_risk_total_simulated: float = Field(
        description="SIMULATED figure — not a real financial estimate."
    )
    estimated_value_at_risk_high_risk_simulated: float = Field(
        description="SIMULATED figure — not a real financial estimate."
    )


class RiskDistributionItem(BaseModel):
    risk_segment: RiskSegment
    customer_count: int
    avg_risk_score: float


class ValueRiskMatrixItem(BaseModel):
    value_segment: ValueSegment
    risk_segment: RiskSegment
    customer_count: int
    estimated_value_at_risk_simulated: float


class TopDriverItem(BaseModel):
    primary_driver: str
    customer_count: int
    estimated_value_at_risk_simulated: float


class SegmentFilterOptions(BaseModel):
    risk_segments: list[str] = ["High", "Medium", "Low"]
    value_segments: list[str] = ["High", "Medium", "Low"]


class CustomerListItem(BaseModel):
    customer_id: str
    value_segment: ValueSegment
    risk_segment: RiskSegment
    risk_score: int
    primary_driver: str
    product_count: int
    balance_change_90d_pct: Optional[float] = None
    card_spend_change_90d_pct: Optional[float] = None
    login_change_90d_pct: Optional[float] = None
    complaint_count_90d: int
    unresolved_contacts_total: int
    recommended_action: str
    recommended_channel: str


class CustomerListResponse(BaseModel):
    items: list[CustomerListItem]
    count: int


class CustomerTrendPoint(BaseModel):
    activity_month: datetime.date
    eom_balance: float
    avg_daily_balance: float
    salary_deposit_flag: int
    card_spend_amount: float
    card_txn_count: int
    declined_txn_count: int
    login_count: int
    session_count: int
    days_since_last_login_eom: int
    product_count: int


class ContactHistoryItem(BaseModel):
    contact_date: datetime.date
    channel: str
    reason: str
    is_complaint: int
    is_resolved: int
    satisfaction_score: int


class CustomerDetailResponse(BaseModel):
    customer_id: str
    signup_date: datetime.date
    tenure_months: int
    age_band: str
    acquisition_channel: str
    home_region: str
    value_segment: ValueSegment
    simulated_annual_value: float
    current_balance: float
    avg_balance_90d: Optional[float] = None
    balance_change_30d_pct: Optional[float] = None
    balance_change_90d_pct: Optional[float] = None
    transfer_out_amount_90d: Optional[float] = None
    salary_deposit_active: int
    salary_deposit_stopped_flag: int
    product_count: int
    product_count_90d_ago: Optional[int] = None
    card_spend_90d: Optional[float] = None
    card_spend_change_30d_pct: Optional[float] = None
    card_spend_change_90d_pct: Optional[float] = None
    declined_txn_count_90d: Optional[int] = None
    days_since_last_login: int
    login_count_90d: Optional[int] = None
    login_change_30d_pct: Optional[float] = None
    login_change_90d_pct: Optional[float] = None
    app_engagement_score: Optional[float] = None
    contact_count_90d: int
    complaint_count_90d: int
    unresolved_contacts_total: int
    avg_satisfaction_score_90d: Optional[float] = None
    campaign_count_12m: int
    campaign_response_rate_12m: float
    campaign_conversion_rate_12m: float
    risk_score: int
    risk_segment: RiskSegment
    primary_driver: str
    secondary_driver: str
    recommended_action: str
    recommended_channel: str
    human_review_required: int
    estimated_value_at_risk: float = Field(description="SIMULATED figure.")
    trends: list[CustomerTrendPoint]
    contact_history: list[ContactHistoryItem]


class RetentionActionItem(BaseModel):
    customer_id: str
    value_segment: ValueSegment
    risk_segment: RiskSegment
    risk_score: int
    primary_driver: str
    secondary_driver: str
    recommended_action: str
    recommended_channel: str
    human_review_required: int
    estimated_value_at_risk: float = Field(description="SIMULATED figure.")
    action_priority_rank: int


class RetentionActionListResponse(BaseModel):
    items: list[RetentionActionItem]
    limit: int
    offset: int


class CrossSellCandidate(BaseModel):
    customer_id: str
    value_segment: ValueSegment
    product_count: int
    app_engagement_score: Optional[float] = None
    complaint_count_90d: int
    risk_segment: RiskSegment


class MlComparisonRow(BaseModel):
    approach: str
    precision: float
    recall: float
    roc_auc: float
    note: str


class PocSummaryResponse(BaseModel):
    synthetic_elements: list[str]
    must_validate_with_bank_data: list[str]
    poc_success_metrics: list[str]
    free_edition_limitations: list[str]
    cross_sell_reuse_note: str
    cross_sell_sample: list[CrossSellCandidate]
    ml_comparison_note: str
    ml_comparison: list[MlComparisonRow]
