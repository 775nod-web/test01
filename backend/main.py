"""Databricks Apps上で動作するFastAPIエントリーポイント。

Reactのビルド成果物（frontend/dist）が存在すればそれを配信し、
存在しない場合はAPIのみで起動する（フロントエンド未ビルドでもAPIは疎通できる）。
"""

from __future__ import annotations

from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.api.routes import router as api_router
from backend.config import resolve_host, resolve_port

FRONTEND_DIST_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"


def create_app() -> FastAPI:
    app = FastAPI(title="顧客休眠予兆・次アクション支援デモ")
    app.include_router(api_router, prefix="/api")

    if FRONTEND_DIST_DIR.is_dir():
        app.mount("/", StaticFiles(directory=FRONTEND_DIST_DIR, html=True), name="frontend")

    return app


app = create_app()


def main() -> None:
    uvicorn.run(app, host=resolve_host(), port=resolve_port())


if __name__ == "__main__":
    main()
