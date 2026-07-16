"""Phase 1 で実装するAPIルート。

`/api/health` と `/api/metadata` のみを提供する。顧客一覧・詳細・予測・推奨・
判断保存・フィードバック概要は後続フェーズで追加する。
"""

from __future__ import annotations

from fastapi import APIRouter

from backend.config import current_timestamp, resolve_data_mode

router = APIRouter()

APP_NAME = "顧客休眠予兆・次アクション支援デモ"
API_VERSION = "0.1.0"


@router.get("/health")
def get_health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/metadata")
def get_metadata() -> dict[str, str]:
    return {
        "app_name": APP_NAME,
        "api_version": API_VERSION,
        "data_mode": resolve_data_mode(),
        "updated_at": current_timestamp(),
    }
