"""APIレスポンスのスキーマ定義（Pydantic）。

顧客360・予測結果のネスト構造は artifacts/ 配下の事前計算済みJSONをそのまま
反映するため、内部の入れ子部分は自由形式（dict）として扱う。データ自体の妥当性は
scripts/prepare_customer360.py と scripts/train_model.py のデータ品質チェックで
生成時点で検証済みである。
"""

from __future__ import annotations

from typing import Any, Optional

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
