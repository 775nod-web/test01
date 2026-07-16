"""data_source.py の Databricks/demo 差し替え境界を検証する。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.services.data_source import load_customer_dataset


def _write_fixture_artifacts(artifacts_dir: Path) -> None:
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    customer360 = {
        "generated_at": "2026-07-16T00:00:00+00:00",
        "as_of_date": "2026-07-16",
        "customer_count": 1,
        "data_sources": ["ec_transactions", "payment_transactions"],
        "customers": [
            {
                "customer_id": "C001",
                "display_name": "顧客 001",
                "services": {},
                "service_count": 1,
                "previous_service_count": 1,
            }
        ],
        "data_quality": {},
    }
    predictions = {
        "model_version": "test-v1",
        "generated_at": "2026-07-16T00:00:00+00:00",
        "predictions": {
            "C001": {
                "churn_probability": 0.5,
                "risk_band": "medium",
                "risk_band_label": "中",
                "reasons": ["テスト用の理由"],
                "model_version": "test-v1",
                "inference_at": "2026-07-16T00:00:00+00:00",
            }
        },
    }
    (artifacts_dir / "customer360.json").write_text(
        json.dumps(customer360, ensure_ascii=False), encoding="utf-8"
    )
    (artifacts_dir / "predictions.json").write_text(
        json.dumps(predictions, ensure_ascii=False), encoding="utf-8"
    )


def test_demo_mode_loads_from_artifacts_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABRICKS_SERVER_HOSTNAME", raising=False)
    monkeypatch.delenv("DATABRICKS_HTTP_PATH", raising=False)
    monkeypatch.delenv("DATABRICKS_TOKEN", raising=False)

    _write_fixture_artifacts(tmp_path)
    dataset = load_customer_dataset(artifacts_dir=tmp_path)

    assert dataset.data_mode == "demo"
    assert dataset.model_mode == "precomputed"
    assert "C001" in dataset.customers_by_id
    assert "C001" in dataset.predictions_by_id


def test_databricks_mode_falls_back_to_demo_when_unimplemented(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATABRICKS_SERVER_HOSTNAME", "example.cloud.databricks.com")
    monkeypatch.setenv("DATABRICKS_HTTP_PATH", "/sql/1.0/warehouses/abc")
    monkeypatch.setenv("DATABRICKS_TOKEN", "dummy-token")

    _write_fixture_artifacts(tmp_path)
    dataset = load_customer_dataset(artifacts_dir=tmp_path)

    # Databricks接続は未実装のため、設定されていてもdemoへフォールバックする。
    assert dataset.data_mode == "demo"
    assert "C001" in dataset.customers_by_id


def test_missing_artifacts_raises_file_not_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABRICKS_SERVER_HOSTNAME", raising=False)
    monkeypatch.delenv("DATABRICKS_HTTP_PATH", raising=False)
    monkeypatch.delenv("DATABRICKS_TOKEN", raising=False)

    empty_dir = tmp_path / "no-artifacts-here"
    with pytest.raises(FileNotFoundError):
        load_customer_dataset(artifacts_dir=empty_dir)
