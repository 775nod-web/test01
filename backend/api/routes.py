"""APIルート。

Phase 1: `/api/health`, `/api/metadata`
Phase 2: `/api/customers`, `/api/customers/{customer_id}`（顧客360＋休眠予測）

推奨アクション・判断保存・フィードバック概要は後続フェーズで追加する。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from backend.config import current_timestamp, resolve_data_mode
from backend.models.schemas import CustomerDetailResponse, CustomersListResponse
from backend.services.customer_service import (
    CustomerNotFoundError,
    get_customer_detail,
    list_customers,
)
from backend.services.data_source import load_customer_dataset

logger = logging.getLogger(__name__)

router = APIRouter()

APP_NAME = "顧客休眠予兆・次アクション支援デモ"
API_VERSION = "0.2.0"


@router.get("/health")
def get_health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/metadata")
def get_metadata() -> dict:
    metadata: dict = {
        "app_name": APP_NAME,
        "api_version": API_VERSION,
        "data_mode": resolve_data_mode(),
        "updated_at": current_timestamp(),
    }

    try:
        dataset = load_customer_dataset()
        metadata["data_mode"] = dataset.data_mode
        metadata["model_mode"] = dataset.model_mode
        metadata["updated_at"] = dataset.updated_at
        metadata["customer_count"] = len(dataset.customers_by_id)
    except FileNotFoundError as exc:
        # 合成データ未生成でもmetadataは200を返す（他のAPIでのみエラーとする）。
        logger.warning("顧客データ未生成のためmetadataは基本情報のみ返します: %s", exc)

    return metadata


@router.get("/customers", response_model=CustomersListResponse)
def get_customers() -> dict:
    try:
        return list_customers()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "顧客データが未生成です。scripts/generate_demo_data.py → "
                "scripts/prepare_customer360.py → scripts/train_model.py を実行してください。"
            ),
        ) from exc


@router.get("/customers/{customer_id}", response_model=CustomerDetailResponse)
def get_customer(customer_id: str) -> dict:
    try:
        return get_customer_detail(customer_id)
    except CustomerNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "顧客データが未生成です。scripts/generate_demo_data.py → "
                "scripts/prepare_customer360.py → scripts/train_model.py を実行してください。"
            ),
        ) from exc
