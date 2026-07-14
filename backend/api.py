"""Fraud Decision Center のAPIルーター。

すべて固定・合成データのみを扱う。外部API・DB・Sparkには依存しない。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from backend import demo_data
from backend.models import (
    CaseDetail,
    CaseListResponse,
    Channel,
    DashboardResponse,
    DecisionRequest,
    DecisionResponse,
    HealthResponse,
    Period,
    Priority,
    RecommendedAction,
    Scenario,
    Status,
)

router = APIRouter(prefix="/api")


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    return HealthResponse()


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(
    scenario: Scenario = Query(default="rules", description="判定方式: rules(既存ルールのみ) または hybrid(ルール＋AI)"),
    period: Period = Query(default="7d", description="期間: 7d または 30d"),
    channel: Channel = Query(default="all", description="チャネル: all, mobile, debit"),
) -> DashboardResponse:
    return demo_data.build_dashboard(scenario=scenario, period=period, channel=channel)


@router.get("/cases", response_model=CaseListResponse)
def get_cases(
    status: Optional[Status] = Query(default=None),
    priority: Optional[Priority] = Query(default=None),
    recommended_action: Optional[RecommendedAction] = Query(default=None),
    risk_band: Optional[str] = Query(default=None, pattern="^(低|中|高)$"),
    q: Optional[str] = Query(default=None, max_length=100, description="取引IDまたは加盟店名の部分一致検索"),
) -> CaseListResponse:
    return demo_data.get_case_list(
        status=status, priority=priority, recommended_action=recommended_action, risk_band=risk_band, query=q,
    )


@router.get("/cases/{transaction_id}", response_model=CaseDetail)
def get_case_detail(transaction_id: str) -> CaseDetail:
    detail = demo_data.get_case_detail(transaction_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"取引ID '{transaction_id}' のケースが見つかりません。")
    return detail


@router.post("/cases/{transaction_id}/decision", response_model=DecisionResponse)
def post_case_decision(transaction_id: str, body: DecisionRequest) -> DecisionResponse:
    updated = demo_data.apply_decision(transaction_id, body.result, body.memo)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"取引ID '{transaction_id}' のケースが見つかりません。")
    return DecisionResponse(**updated)
