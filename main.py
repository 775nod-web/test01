"""Fraud Decision Center — Databricks Apps エントリポイント。

FastAPI 1プロセスで /api/* と、ビルド済みReact静的ファイル(static/)を
同一オリジンで配信する。外部DB・外部API・Sparkには依存しない。
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.api import router as api_router

logger = logging.getLogger("fraud_decision_center")

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="Fraud Decision Center API",
    description="不正対策デモ(合成データのみ)のバックエンドAPIです。",
    version="0.1.0",
)

app.include_router(api_router)

if (STATIC_DIR / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error while processing %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "内部エラーが発生しました。時間をおいて再度お試しください。"})


@app.get("/{full_path:path}", include_in_schema=False, response_model=None)
def serve_spa(full_path: str) -> FileResponse | JSONResponse:
    if full_path.startswith("api/"):
        return JSONResponse(status_code=404, content={"detail": "指定されたAPIパスが見つかりません。"})

    index_path = STATIC_DIR / "index.html"
    if not index_path.is_file():
        return JSONResponse(
            status_code=503,
            content={
                "detail": (
                    "フロントエンドのビルド成果物(static/)が見つかりません。"
                    "`npm run build` を実行してからアプリを起動してください。"
                )
            },
        )

    candidate = (STATIC_DIR / full_path).resolve()
    if full_path and candidate.is_file() and STATIC_DIR.resolve() in candidate.parents:
        return FileResponse(candidate)

    return FileResponse(index_path)
