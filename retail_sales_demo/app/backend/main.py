"""Serving layer REST API for the retail POS sales analysis demo.

Exposes the four Gold layer tables to the React frontend over HTTP, querying
them through the Serverless SQL Warehouse configured via
`DATABRICKS_WAREHOUSE_ID` (see config.py).

Every endpoint accepts an optional `store_id` filter (comma-separated for
multiple stores). Since Phase 3, this is intersected with the caller's
allowed stores (access_control.py) before it ever reaches a query builder —
see docs/phase3_governance_and_ops.md for why this is an API-layer fallback
rather than a database-level guarantee.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import access_control, audit, config, queries
from .access_control import AccessContext
from .db import run_query

app = FastAPI(
    title="retail_sales_demo serving layer API",
    description=(
        "Gold layer(workspace.gold)の集計データをReactフロントエンド向けに"
        "REST API化するServing layer。"
    ),
    version="0.1.0",
)

GROSS_SALES_NOTE = (
    "gold_daily_store_sales / gold_category_sales には discount 集約列が存在しないため、"
    "gross_sales は net_sales と同値の暫定値です。正確な gross sales の算出には "
    "Gold layer への discount 集約列の追加が必要です。"
)


def _parse_csv(value: Optional[str]) -> Optional[List[str]]:
    if not value:
        return None
    parsed = [item.strip() for item in value.split(",") if item.strip()]
    return parsed or None


def get_access_context(request: Request) -> AccessContext:
    user_email = access_control.resolve_user_email(request)
    return access_control.get_access_context(user_email)


@app.middleware("http")
async def audit_log_middleware(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        user_email = access_control.resolve_user_email(request)
        audit.record_access(
            user_email=user_email,
            endpoint=request.url.path,
            store_id_filter=request.query_params.get("store_id"),
            status_code=response.status_code,
        )
    return response


StoreIdParam = Query(
    None,
    alias="store_id",
    description="カンマ区切りの店舗IDで絞り込み（例: S001,S002）。未指定なら、呼び出し元に許可された全店舗。",
)
DateFromParam = Query(None, description="集計期間の開始日（含む、YYYY-MM-DD）")
DateToParam = Query(None, description="集計期間の終了日（含む、YYYY-MM-DD）")


class MeResponse(BaseModel):
    user_email: str
    allowed_store_ids: Optional[List[str]]  # null means "every store" (admin/HQ)
    roles: List[str]


@app.get("/api/me", response_model=MeResponse)
def me(context: AccessContext = Depends(get_access_context)) -> MeResponse:
    return MeResponse(
        user_email=context.user_email,
        allowed_store_ids=context.allowed_store_ids,
        roles=sorted(context.roles),
    )


class KpiSummaryResponse(BaseModel):
    net_sales: float
    gross_sales: float
    gross_sales_is_estimated: bool
    gross_sales_note: str
    transaction_count: int
    units_sold: int
    average_basket_size: Optional[float]


@app.get("/api/kpi-summary", response_model=KpiSummaryResponse)
def kpi_summary(
    store_id: Optional[str] = StoreIdParam,
    date_from: Optional[date] = DateFromParam,
    date_to: Optional[date] = DateToParam,
    context: AccessContext = Depends(get_access_context),
) -> KpiSummaryResponse:
    effective_store_ids = access_control.resolve_effective_store_ids(
        _parse_csv(store_id), context.allowed_store_ids
    )
    if effective_store_ids == []:
        return KpiSummaryResponse(
            net_sales=0,
            gross_sales=0,
            gross_sales_is_estimated=True,
            gross_sales_note=GROSS_SALES_NOTE,
            transaction_count=0,
            units_sold=0,
            average_basket_size=None,
        )
    sql, params = queries.build_kpi_summary_query(effective_store_ids, date_from, date_to)
    rows = run_query(sql, params)
    row = rows[0] if rows else {}
    net_sales = float(row.get("net_sales") or 0)
    transaction_count = int(row.get("transaction_count") or 0)
    units_sold = int(row.get("units_sold") or 0)
    average_basket_size = (net_sales / transaction_count) if transaction_count else None
    return KpiSummaryResponse(
        net_sales=net_sales,
        gross_sales=net_sales,
        gross_sales_is_estimated=True,
        gross_sales_note=GROSS_SALES_NOTE,
        transaction_count=transaction_count,
        units_sold=units_sold,
        average_basket_size=average_basket_size,
    )


class DailyStoreSalesPoint(BaseModel):
    sales_date: date
    store_id: str
    store_name: str
    net_sales: float
    transaction_count: int
    units_sold: int


@app.get("/api/daily-store-sales", response_model=List[DailyStoreSalesPoint])
def daily_store_sales(
    store_id: Optional[str] = StoreIdParam,
    date_from: Optional[date] = DateFromParam,
    date_to: Optional[date] = DateToParam,
    context: AccessContext = Depends(get_access_context),
) -> list[dict]:
    effective_store_ids = access_control.resolve_effective_store_ids(
        _parse_csv(store_id), context.allowed_store_ids
    )
    if effective_store_ids == []:
        return []
    sql, params = queries.build_daily_store_sales_query(effective_store_ids, date_from, date_to)
    return run_query(sql, params)


class CategorySalesPoint(BaseModel):
    category_id: str
    category_name: str
    net_sales: float
    units_sold: int
    share_of_net_sales: Optional[float]


@app.get("/api/category-sales", response_model=List[CategorySalesPoint])
def category_sales(
    store_id: Optional[str] = StoreIdParam,
    date_from: Optional[date] = DateFromParam,
    date_to: Optional[date] = DateToParam,
    context: AccessContext = Depends(get_access_context),
) -> list[dict]:
    effective_store_ids = access_control.resolve_effective_store_ids(
        _parse_csv(store_id), context.allowed_store_ids
    )
    if effective_store_ids == []:
        return []
    sql, params = queries.build_category_sales_query(effective_store_ids, date_from, date_to)
    rows = run_query(sql, params)
    total_net_sales = sum(float(row.get("net_sales") or 0) for row in rows)
    for row in rows:
        row["net_sales"] = float(row.get("net_sales") or 0)
        row["share_of_net_sales"] = (row["net_sales"] / total_net_sales) if total_net_sales else None
    return rows


class StoreRankingPoint(BaseModel):
    ranking_date: date
    store_id: str
    store_name: str
    net_sales: float
    rank: int


@app.get("/api/store-ranking", response_model=List[StoreRankingPoint])
def store_ranking(
    store_id: Optional[str] = StoreIdParam,
    date_from: Optional[date] = DateFromParam,
    date_to: Optional[date] = DateToParam,
    context: AccessContext = Depends(get_access_context),
) -> list[dict]:
    effective_store_ids = access_control.resolve_effective_store_ids(
        _parse_csv(store_id), context.allowed_store_ids
    )
    if effective_store_ids == []:
        return []
    sql, params = queries.build_store_ranking_query(effective_store_ids, date_from, date_to)
    return run_query(sql, params)


class QuarantineReportItem(BaseModel):
    transaction_date: date
    transaction_id: str
    store_id: Optional[str]
    product_id: Optional[str]
    issue_type: str
    net_sales: Optional[float]
    quantity: Optional[int]
    customer_id: Optional[str]
    customer_id_is_masked: bool


@app.get("/api/quarantine-report", response_model=List[QuarantineReportItem])
def quarantine_report(
    store_id: Optional[str] = StoreIdParam,
    issue_type: Optional[str] = Query(
        None, description="カンマ区切りのissue_typeで絞り込み（例: UNKNOWN_PRODUCT,UNKNOWN_STORE）"
    ),
    date_from: Optional[date] = DateFromParam,
    date_to: Optional[date] = DateToParam,
    context: AccessContext = Depends(get_access_context),
) -> list[dict]:
    effective_store_ids = access_control.resolve_effective_store_ids(
        _parse_csv(store_id), context.allowed_store_ids
    )
    if effective_store_ids == []:
        return []
    sql, params = queries.build_quarantine_report_query(
        effective_store_ids, _parse_csv(issue_type), date_from, date_to
    )
    rows = run_query(sql, params)
    for row in rows:
        row["customer_id_is_masked"] = not context.can_view_pii
        if not context.can_view_pii:
            row["customer_id"] = access_control.mask_customer_id(row.get("customer_id"))
    return rows


class AlertItem(BaseModel):
    alert_date: date
    store_id: str
    store_name: str
    comparison_type: str
    current_value: float
    previous_value: float
    pct_change: float
    threshold_pct: float


@app.get("/api/alerts", response_model=List[AlertItem])
def alerts(
    store_id: Optional[str] = StoreIdParam,
    context: AccessContext = Depends(get_access_context),
) -> list[dict]:
    """Reads the most recent day's rows from gold_store_sales_alerts, written
    by jobs/alert_batch.py (see docs/phase3_governance_and_ops.md — the batch
    job itself is written but not yet deployed/verified against a live
    workspace, so this table may not exist yet)."""
    effective_store_ids = access_control.resolve_effective_store_ids(
        _parse_csv(store_id), context.allowed_store_ids
    )
    if effective_store_ids == []:
        return []
    sql, params = queries.build_alerts_query(effective_store_ids)
    return run_query(sql, params)


class AuditLogEntry(BaseModel):
    logged_at: str
    user_email: str
    endpoint: str
    store_id_filter: Optional[str]
    status_code: int


@app.get("/api/audit-log", response_model=List[AuditLogEntry])
def audit_log(
    limit: int = Query(200, ge=1, le=1000),
    context: AccessContext = Depends(get_access_context),
) -> list[dict]:
    if not context.can_view_audit_log:
        raise HTTPException(status_code=403, detail="監査ログの閲覧権限がありません（AUDIT_VIEWERロールが必要）")
    sql, params = queries.build_audit_log_query(limit)
    return run_query(sql, params)


class RequeueStatusResponse(BaseModel):
    run_id: Optional[str]
    started_at: Optional[str]
    status: Optional[str]
    records_checked: Optional[int]
    reconciled_candidates_found: Optional[int]


@app.get("/api/requeue-status", response_model=RequeueStatusResponse)
def requeue_status() -> RequeueStatusResponse:
    """Reads the latest run summary from gold_requeue_batch_runs, written by
    jobs/requeue_batch.py. Same caveat as /api/alerts: the batch is written
    but not deployed/verified — this table may not exist yet."""
    sql, params = queries.build_requeue_status_query()
    rows = run_query(sql, params)
    if not rows:
        return RequeueStatusResponse(
            run_id=None, started_at=None, status=None, records_checked=None, reconciled_candidates_found=None
        )
    row = rows[0]
    return RequeueStatusResponse(
        run_id=row.get("run_id"),
        started_at=str(row["started_at"]) if row.get("started_at") is not None else None,
        status=row.get("status"),
        records_checked=row.get("records_checked"),
        reconciled_candidates_found=row.get("reconciled_candidates_found"),
    )


class RequeueTriggerResponse(BaseModel):
    triggered: bool
    run_id: Optional[str]
    message: str


@app.post("/api/requeue-trigger", response_model=RequeueTriggerResponse)
def requeue_trigger() -> RequeueTriggerResponse:
    """Triggers jobs/requeue_batch.py via the Databricks Jobs API (run-now).

    Requires REQUEUE_JOB_ID (config.py) to be set to the deployed job's ID —
    see retail_sales_demo/jobs/resources/requeue_batch_job.json. That
    deployment has not happened from this session (no workspace access), so
    this returns a clear 501 rather than silently pretending to succeed.
    """
    if not config.REQUEUE_JOB_ID:
        raise HTTPException(
            status_code=501,
            detail=(
                "REQUEUE_JOB_ID が未設定です。jobs/resources/requeue_batch_job.json を"
                "ワークスペースにデプロイし、発行されたjob_idを環境変数 REQUEUE_JOB_ID に設定してください。"
            ),
        )
    from databricks.sdk import WorkspaceClient  # imported lazily: only needed on this path

    client = WorkspaceClient()
    run = client.jobs.run_now(job_id=int(config.REQUEUE_JOB_ID))
    return RequeueTriggerResponse(triggered=True, run_id=str(run.run_id), message="再照合ジョブを起動しました。")


# Serves the built React SPA (Phase 2) from the same process/origin as the
# /api/* routes above, so the frontend can call them as relative paths with
# no CORS setup. `npm run build` in frontend/ writes straight into this
# directory (see frontend/vite.config.ts); it's absent until that build has
# run, so plain API development/testing doesn't require a frontend build.
_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if _STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="frontend")
