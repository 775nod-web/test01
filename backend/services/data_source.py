"""顧客360・予測データの取得口。

CLAUDE.mdの方針に従い、Databricks利用時とデモデータ利用時の差し替え境界をここに置く。
Free Edition向けの実際のDatabricks SQL/Unity Catalog接続はこのフェーズの対象外であり、
`_load_from_databricks` は明示的に未実装として例外を送出し、demoデータへフォールバックする
（本番で追加する接続処理の差し込み口として、この関数を置き換える想定）。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from backend.config import DATA_MODE_DATABRICKS, resolve_data_mode

logger = logging.getLogger(__name__)

ARTIFACTS_DIR = Path(__file__).resolve().parent.parent.parent / "artifacts"


class DatabricksUnavailableError(RuntimeError):
    """Databricks SQLからの取得が未実装、または失敗した場合に送出する。"""


@dataclass
class CustomerDataset:
    data_mode: str  # 実際にデータを供給したモード（"demo" または "databricks"）
    updated_at: str
    model_mode: str
    customers_by_id: dict[str, dict]
    predictions_by_id: dict[str, dict]


def _load_from_databricks() -> CustomerDataset:
    """Unity Catalog / Databricks SQLからの取得口（本フェーズでは未実装）。

    本番化時にここへ実際のクエリ処理を実装する。取得に失敗した場合は
    DatabricksUnavailableError を送出し、呼び出し側でdemoデータへフォールバックする。
    """
    raise DatabricksUnavailableError(
        "Databricks SQLへの接続は未実装のため、合成データ（demo）へフォールバックします。"
    )


def _load_from_demo(artifacts_dir: Path) -> CustomerDataset:
    customer360_path = artifacts_dir / "customer360.json"
    predictions_path = artifacts_dir / "predictions.json"

    if not customer360_path.exists() or not predictions_path.exists():
        raise FileNotFoundError(
            f"{customer360_path} または {predictions_path} が見つかりません。"
            "scripts/generate_demo_data.py → scripts/prepare_customer360.py → "
            "scripts/train_model.py の順に実行してください。"
        )

    with customer360_path.open(encoding="utf-8") as f:
        customer360 = json.load(f)
    with predictions_path.open(encoding="utf-8") as f:
        predictions_payload = json.load(f)

    customers_by_id = {c["customer_id"]: c for c in customer360["customers"]}
    predictions_by_id = predictions_payload["predictions"]

    updated_at = max(customer360["generated_at"], predictions_payload["generated_at"])

    return CustomerDataset(
        data_mode="demo",
        updated_at=updated_at,
        model_mode="precomputed",
        customers_by_id=customers_by_id,
        predictions_by_id=predictions_by_id,
    )


def load_customer_dataset(artifacts_dir: Optional[Path] = None) -> CustomerDataset:
    """設定されたデータモードに応じてデータセットを取得する。

    databricksモードで取得できない場合はdemoデータへフォールバックする
    （CLAUDE.mdの「Free Editionで接続設定が難しい場合に備え、合成データへ
    フォールバックできるようにする」という方針に対応する）。
    """
    resolved_artifacts_dir = artifacts_dir if artifacts_dir is not None else ARTIFACTS_DIR

    configured_mode = resolve_data_mode()
    if configured_mode == DATA_MODE_DATABRICKS:
        try:
            return _load_from_databricks()
        except DatabricksUnavailableError as exc:
            logger.warning(str(exc))

    return _load_from_demo(resolved_artifacts_dir)
