"""APIレスポンスのスキーマ定義（Pydantic）。

顧客360・予測結果のネスト構造は artifacts/ 配下の事前計算済みJSONをそのまま
反映するため、内部の入れ子部分は自由形式（dict）として扱う。データ自体の妥当性は
scripts/prepare_customer360.py と scripts/train_model.py のデータ品質チェックで
生成時点で検証済みである。
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel


class CustomerSummary(BaseModel):
    customer_id: str
    display_name: str
    risk_band: str
    risk_band_label: str
    churn_probability: float
    service_count: int
    previous_service_count: int
    top_reason: Optional[str] = None


class CustomersListResponse(BaseModel):
    data_mode: str
    model_mode: str
    updated_at: str
    customers: list[CustomerSummary]


class CustomerDetailResponse(BaseModel):
    data_mode: str
    model_mode: str
    updated_at: str
    customer: dict[str, Any]
    prediction: dict[str, Any]


class ActionCandidate(BaseModel):
    title: str
    reason: str


class ReferenceItem(BaseModel):
    doc_id: str
    title: str
    type: str


class RecommendationResponse(BaseModel):
    customer_id: str
    generation_mode: Literal["llm", "pre_generated", "rule_based"]
    generation_mode_label: str
    model_version: str
    generated_at: str
    summary: str
    actions: list[ActionCandidate]
    cautions: list[str]
    references: list[ReferenceItem]


class DecisionRequest(BaseModel):
    decision: Literal["approved", "modified", "skipped"]
    selected_action: Optional[str] = None
    modified_text: Optional[str] = None
    comment: Optional[str] = None
    generation_mode: Optional[str] = None
    model_version: Optional[str] = None


class DecisionRecord(BaseModel):
    decision_id: str
    customer_id: str
    decision: Literal["approved", "modified", "skipped"]
    selected_action: Optional[str] = None
    modified_text: Optional[str] = None
    comment: Optional[str] = None
    decided_at: str
    generation_mode: Optional[str] = None
    model_version: Optional[str] = None


class FeedbackSummaryResponse(BaseModel):
    total_decisions: int
    approved_count: int
    modified_count: int
    skipped_count: int
    by_generation_mode: dict[str, int]
    recent_decisions: list[dict[str, Any]]
    updated_at: str
    note: str
