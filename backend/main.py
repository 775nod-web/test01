"""
FastAPI backend for the bank customer retention demo. Serves the built
React frontend (backend/static/, produced by `npm run build` in
frontend/) and exposes typed /api/* endpoints backed by Databricks SQL
(production) or a local DuckDB fixture (dev only) — see backend/db.py.

Production entrypoint (matches app.yaml): `python backend/main.py`, which
binds to 0.0.0.0 and DATABRICKS_APP_PORT.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.db import QueryError, get_query_engine, LocalDuckDBQueryEngine
from backend.schemas import (
    CustomerDetailResponse,
    CustomerListResponse,
    HealthResponse,
    KpiResponse,
    PocSummaryResponse,
    RetentionActionListResponse,
    RiskDistributionItem,
    SegmentFilterOptions,
    TopDriverItem,
    ValueRiskMatrixItem,
)
from backend.services import analytics, customers, poc, retention

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_title, version=settings.app_version)

STATIC_DIR = Path(__file__).resolve().parent / "static"


def _engine():
    try:
        return get_query_engine()
    except QueryError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _handle_query_error(exc: QueryError) -> None:
    logger.error("Query failed: %s", exc)
    raise HTTPException(status_code=500, detail="A data query failed. Check server logs.") from exc


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    engine = _engine()
    data_mode = "local" if isinstance(engine, LocalDuckDBQueryEngine) else "databricks"
    try:
        engine.health_check()
        return HealthResponse(status="ok", data_mode=data_mode)
    except Exception as exc:  # noqa: BLE001 — health endpoint reports, doesn't propagate
        return HealthResponse(status="error", data_mode=data_mode, detail=str(exc))


@app.get("/api/kpis", response_model=KpiResponse)
def get_kpis() -> KpiResponse:
    try:
        return KpiResponse(**analytics.get_kpis(_engine()))
    except QueryError as exc:
        _handle_query_error(exc)
    except LookupError as exc:
        raise HTTPException(status_code=500, detail="executive_kpis has no data yet.") from exc


@app.get("/api/risk-distribution", response_model=list[RiskDistributionItem])
def get_risk_distribution() -> list[RiskDistributionItem]:
    try:
        rows = analytics.get_risk_distribution(_engine())
        return [RiskDistributionItem(**r) for r in rows]
    except QueryError as exc:
        _handle_query_error(exc)


@app.get("/api/value-risk-matrix", response_model=list[ValueRiskMatrixItem])
def get_value_risk_matrix() -> list[ValueRiskMatrixItem]:
    try:
        rows = analytics.get_value_risk_matrix(_engine())
        return [ValueRiskMatrixItem(**r) for r in rows]
    except QueryError as exc:
        _handle_query_error(exc)


@app.get("/api/top-risk-drivers", response_model=list[TopDriverItem])
def get_top_risk_drivers() -> list[TopDriverItem]:
    try:
        rows = analytics.get_top_risk_drivers(_engine())
        return [TopDriverItem(**r) for r in rows]
    except QueryError as exc:
        _handle_query_error(exc)


@app.get("/api/segments", response_model=SegmentFilterOptions)
def get_segment_filter_options() -> SegmentFilterOptions:
    # Risk/value segments are a fixed, documented vocabulary (docs/risk-scoring.md),
    # not discovered from data, so this is intentionally static.
    return SegmentFilterOptions()


@app.get("/api/customers", response_model=CustomerListResponse)
def list_customers(
    risk_segment: Optional[str] = Query(default=None, pattern="^(High|Medium|Low)$"),
    value_segment: Optional[str] = Query(default=None, pattern="^(High|Medium|Low)$"),
    max_product_count: Optional[int] = Query(default=None, ge=0, le=20),
    balance_decline_pct: Optional[float] = Query(default=None, ge=-1.0, le=0.0),
    card_spend_decline_pct: Optional[float] = Query(default=None, ge=-1.0, le=0.0),
    app_decline_pct: Optional[float] = Query(default=None, ge=-1.0, le=0.0),
    min_complaints_90d: Optional[int] = Query(default=None, ge=0, le=100),
    limit: int = Query(default=200, ge=1, le=2000),
) -> CustomerListResponse:
    try:
        rows = customers.list_customers(
            _engine(),
            risk_segment=risk_segment,
            value_segment=value_segment,
            max_product_count=max_product_count,
            balance_decline_pct=balance_decline_pct,
            card_spend_decline_pct=card_spend_decline_pct,
            app_decline_pct=app_decline_pct,
            min_complaints_90d=min_complaints_90d,
            limit=limit,
        )
        return CustomerListResponse(items=rows, count=len(rows))
    except QueryError as exc:
        _handle_query_error(exc)


@app.get("/api/customers/{customer_id}", response_model=CustomerDetailResponse)
def get_customer_detail(customer_id: str) -> CustomerDetailResponse:
    try:
        detail = customers.get_customer_detail(_engine(), customer_id)
    except QueryError as exc:
        _handle_query_error(exc)
        return  # unreachable, satisfies type checkers
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Customer '{customer_id}' not found.")
    return CustomerDetailResponse(**detail)


@app.get("/api/retention-actions", response_model=RetentionActionListResponse)
def get_retention_actions(
    risk_segment: Optional[str] = Query(default=None, pattern="^(High|Medium)$"),
    value_segment: Optional[str] = Query(default=None, pattern="^(High|Medium|Low)$"),
    limit: int = Query(default=100, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
) -> RetentionActionListResponse:
    try:
        rows = retention.list_retention_actions(
            _engine(), risk_segment=risk_segment, value_segment=value_segment, limit=limit, offset=offset
        )
        return RetentionActionListResponse(items=rows, limit=limit, offset=offset)
    except QueryError as exc:
        _handle_query_error(exc)


@app.get("/api/retention-actions/export")
def export_retention_actions(
    risk_segment: Optional[str] = Query(default=None, pattern="^(High|Medium)$"),
    value_segment: Optional[str] = Query(default=None, pattern="^(High|Medium|Low)$"),
) -> PlainTextResponse:
    try:
        csv_text = retention.export_retention_actions_csv(
            _engine(), risk_segment=risk_segment, value_segment=value_segment
        )
        return PlainTextResponse(
            content=csv_text,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=retention_actions.csv"},
        )
    except QueryError as exc:
        _handle_query_error(exc)


@app.get("/api/poc-summary", response_model=PocSummaryResponse)
def get_poc_summary() -> PocSummaryResponse:
    try:
        return PocSummaryResponse(**poc.get_poc_summary(_engine()))
    except QueryError as exc:
        _handle_query_error(exc)


# --- Static frontend (must be registered after all /api routes) ---

if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str) -> FileResponse:
        index_path = STATIC_DIR / "index.html"
        return FileResponse(index_path)
else:
    logger.warning(
        "backend/static/ not found — the frontend hasn't been built yet. "
        "Run `npm run build` (root package.json) before deploying. API "
        "endpoints under /api/* still work."
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=settings.app_port)
