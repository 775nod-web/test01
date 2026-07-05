"""Serving layer REST API for the retail POS sales analysis demo.

Exposes the four Gold layer tables to the React frontend over HTTP, querying
them through the Serverless SQL Warehouse configured via
`DATABRICKS_WAREHOUSE_ID` (see config.py).

Every endpoint accepts an optional `store_id` filter (comma-separated for
multiple stores) so that Phase 3's per-user store access control can be
layered on top: that phase only needs to intersect the caller's allowed
store IDs with whatever `store_id` was requested, without changing any
query-building code here.
"""
from __future__ import annotations

from datetime import date
from typing import List, Optional

from fastapi import FastAPI, Query
from pydantic import BaseModel

from . import queries
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


StoreIdParam = Query(
    None,
    alias="store_id",
    description="カンマ区切りの店舗IDで絞り込み（例: S001,S002）。未指定なら全店舗。",
)
DateFromParam = Query(None, description="集計期間の開始日（含む、YYYY-MM-DD）")
DateToParam = Query(None, description="集計期間の終了日（含む、YYYY-MM-DD）")


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
) -> KpiSummaryResponse:
    sql, params = queries.build_kpi_summary_query(_parse_csv(store_id), date_from, date_to)
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
) -> list[dict]:
    sql, params = queries.build_daily_store_sales_query(_parse_csv(store_id), date_from, date_to)
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
) -> list[dict]:
    sql, params = queries.build_category_sales_query(_parse_csv(store_id), date_from, date_to)
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
) -> list[dict]:
    sql, params = queries.build_store_ranking_query(_parse_csv(store_id), date_from, date_to)
    return run_query(sql, params)


class QuarantineReportItem(BaseModel):
    transaction_date: date
    transaction_id: str
    store_id: Optional[str]
    product_id: Optional[str]
    issue_type: str
    net_sales: Optional[float]
    quantity: Optional[int]


@app.get("/api/quarantine-report", response_model=List[QuarantineReportItem])
def quarantine_report(
    store_id: Optional[str] = StoreIdParam,
    issue_type: Optional[str] = Query(
        None, description="カンマ区切りのissue_typeで絞り込み（例: UNKNOWN_PRODUCT,UNKNOWN_STORE）"
    ),
    date_from: Optional[date] = DateFromParam,
    date_to: Optional[date] = DateToParam,
) -> list[dict]:
    sql, params = queries.build_quarantine_report_query(
        _parse_csv(store_id), _parse_csv(issue_type), date_from, date_to
    )
    return run_query(sql, params)
