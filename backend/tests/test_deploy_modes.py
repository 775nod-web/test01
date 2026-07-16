"""デプロイ前ビルド方式に伴う、development/productionモードの起動挙動を検証する。

frontend/dist の実体には触れず、一時ディレクトリでdist有無を再現することで、
リポジトリ内の実際のビルド成果物の状態に依存せずテストできるようにする。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import FrontendBuildMissingError, create_app


def test_development_mode_starts_without_dist(tmp_path: Path) -> None:
    missing_dist = tmp_path / "no-such-dist"
    app = create_app(app_env="development", frontend_dist_dir=missing_dist)
    client = TestClient(app)

    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_production_mode_raises_without_dist(tmp_path: Path) -> None:
    missing_dist = tmp_path / "no-such-dist"

    with pytest.raises(FrontendBuildMissingError) as excinfo:
        create_app(app_env="production", frontend_dist_dir=missing_dist)

    assert "frontend/dist/index.html" in str(excinfo.value)
    assert "scripts/prepare_deploy.sh" in str(excinfo.value)


def test_production_mode_starts_and_serves_index_when_dist_exists(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    marker = "デプロイ前ビルド確認用マーカー"
    (dist_dir / "index.html").write_text(
        f"<!doctype html><html><body>{marker}</body></html>", encoding="utf-8"
    )

    app = create_app(app_env="production", frontend_dist_dir=dist_dir)
    client = TestClient(app)

    health_response = client.get("/api/health")
    assert health_response.status_code == 200

    index_response = client.get("/")
    assert index_response.status_code == 200
    assert marker in index_response.text


def test_reload_at_root_serves_spa_index_repeatedly(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    (dist_dir / "index.html").write_text(
        "<!doctype html><html><body>spa</body></html>", encoding="utf-8"
    )

    app = create_app(app_env="production", frontend_dist_dir=dist_dir)
    client = TestClient(app)

    for _ in range(2):
        response = client.get("/")
        assert response.status_code == 200
        assert "spa" in response.text


def test_unknown_non_api_path_falls_back_to_spa_index(tmp_path: Path) -> None:
    """未知のパス（直リンクやリロード）でも/api/*以外はindex.htmlへフォールバックする。"""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    (dist_dir / "index.html").write_text(
        "<!doctype html><html><body>spa</body></html>", encoding="utf-8"
    )

    app = create_app(app_env="production", frontend_dist_dir=dist_dir)
    client = TestClient(app)

    response = client.get("/some/unknown/route")
    assert response.status_code == 200
    assert "spa" in response.text


def test_unknown_api_path_stays_json_404_not_spa_index(tmp_path: Path) -> None:
    """/api/*の404はindex.htmlへ差し替えず、JSON詳細メッセージのまま返す
    （静的ファイル配信とAPIルートが競合しないことの確認）。"""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    (dist_dir / "index.html").write_text(
        "<!doctype html><html><body>spa</body></html>", encoding="utf-8"
    )

    app = create_app(app_env="production", frontend_dist_dir=dist_dir)
    client = TestClient(app)

    response = client.get("/api/customers/NOPE")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    assert "NOPE" in response.json()["detail"]


def test_unknown_path_without_dist_returns_plain_404(tmp_path: Path) -> None:
    """distが無いdevelopmentモードでは、SPAフォールバックは適用されず通常の404になる。"""
    missing_dist = tmp_path / "no-such-dist"
    app = create_app(app_env="development", frontend_dist_dir=missing_dist)
    client = TestClient(app)

    response = client.get("/some/unknown/route")
    assert response.status_code == 404
