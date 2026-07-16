"""判断（承認／修正／見送り）の保存。

デモ環境では永続ストレージが未設定でも動作するよう、軽量なJSONファイルへ保存する。
Databricks側の保存先（例: Delta テーブル）が設定されている場合に差し替えられるよう、
`backend/services/data_source.py` と同じ「試行してダメならフォールバック」の
設計パターンを踏襲する。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from backend.config import DATA_MODE_DATABRICKS, resolve_data_mode

logger = logging.getLogger(__name__)

DEFAULT_DECISIONS_PATH = Path(__file__).resolve().parent.parent.parent / "runtime" / "decisions.json"


class DecisionStorageUnavailableError(RuntimeError):
    """Databricks側の判断保存先が未実装、または利用できない場合に送出する。"""


class FileDecisionStore:
    """判断をJSONファイルへ保存する軽量なストレージ（デモ用の既定実装）。"""

    def __init__(self, path: Path) -> None:
        self._path = path

    def _read_all(self) -> list[dict]:
        if not self._path.exists():
            return []
        with self._path.open(encoding="utf-8") as f:
            return json.load(f)

    def save_decision(self, record: dict) -> dict:
        records = self._read_all()
        decision_id = f"D{len(records) + 1:05d}"
        saved_record = {"decision_id": decision_id, **record}
        records.append(saved_record)

        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
            f.write("\n")

        return saved_record

    def list_decisions(self) -> list[dict]:
        return self._read_all()


def _get_databricks_store() -> FileDecisionStore:
    """Databricks側の判断保存先への差し替え口（本フェーズでは未実装）。

    本番化時にここへ実際の保存処理（例: Delta テーブルへのINSERT）を実装する。
    """
    raise DecisionStorageUnavailableError(
        "Databricksへの判断保存は未実装のため、ファイルストレージへフォールバックします。"
    )


def get_decision_store(path: Optional[Path] = None):
    """設定されたデータモードに応じて判断ストレージを取得する。

    databricksモードで取得できない場合はファイルストレージへフォールバックする。
    """
    resolved_path = path if path is not None else DEFAULT_DECISIONS_PATH

    configured_mode = resolve_data_mode()
    if configured_mode == DATA_MODE_DATABRICKS:
        try:
            return _get_databricks_store()
        except DecisionStorageUnavailableError as exc:
            logger.warning(str(exc))

    return FileDecisionStore(resolved_path)
