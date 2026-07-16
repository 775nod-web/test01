"""判断（承認／修正／見送り）の保存。

デモ環境では永続ストレージが未設定でも動作するよう、軽量なJSONファイルへ保存する。
Databricks側の保存先（例: Delta テーブル）が設定されている場合に差し替えられるよう、
`backend/services/data_source.py` と同じ「試行してダメならフォールバック」の
設計パターンを踏襲する。

Databricks Apps環境ではコンテナのファイルシステムが読み取り専用、または
再起動で内容が失われる場合がある。書き込みができない場合は、エラーで
判断保存自体を失敗させるのではなく、プロセス内メモリへ安全にフォールバックし、
`persisted=False` をレスポンスへ含めることで、利用者が「この判断は永続化されて
いない」ことを画面上で把握できるようにする。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional, Protocol

from backend.config import DATA_MODE_DATABRICKS, resolve_data_mode

logger = logging.getLogger(__name__)

DEFAULT_DECISIONS_PATH = Path(__file__).resolve().parent.parent.parent / "runtime" / "decisions.json"

STORAGE_MODE_FILE = "file"
STORAGE_MODE_MEMORY = "memory"
STORAGE_MODE_DATABRICKS = "databricks"


class DecisionStorageUnavailableError(RuntimeError):
    """Databricks側の判断保存先が未実装、または利用できない場合に送出する。"""


class DecisionStore(Protocol):
    storage_mode: str
    persisted: bool

    def save_decision(self, record: dict) -> dict: ...

    def list_decisions(self) -> list[dict]: ...


class FileDecisionStore:
    """判断をJSONファイルへ保存する軽量なストレージ（デモ用の既定実装）。"""

    storage_mode = STORAGE_MODE_FILE
    persisted = True

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
        saved_record = {"decision_id": decision_id, **record, "persisted": True}
        records.append(saved_record)

        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
            f.write("\n")

        return saved_record

    def list_decisions(self) -> list[dict]:
        return self._read_all()


class InMemoryDecisionStore:
    """書き込み先が読み取り専用・利用不可の場合の安全なフォールバック。

    プロセスが再起動すると内容は失われる（`persisted=False`）。
    """

    storage_mode = STORAGE_MODE_MEMORY
    persisted = False

    def __init__(self) -> None:
        self._records: list[dict] = []

    def save_decision(self, record: dict) -> dict:
        decision_id = f"D{len(self._records) + 1:05d}"
        saved_record = {"decision_id": decision_id, **record, "persisted": False}
        self._records.append(saved_record)
        return saved_record

    def list_decisions(self) -> list[dict]:
        return list(self._records)


# ファイルストレージが書き込み不可と判明した場合、プロセス内で一貫したフォールバック
# ストアを使い続けるための共有インスタンス（呼び出しごとに新規作成すると、
# 直前に保存した判断がlist_decisionsへ反映されなくなるため）。
_shared_in_memory_store: Optional[InMemoryDecisionStore] = None


def _get_shared_in_memory_store() -> InMemoryDecisionStore:
    global _shared_in_memory_store
    if _shared_in_memory_store is None:
        _shared_in_memory_store = InMemoryDecisionStore()
    return _shared_in_memory_store


def _is_directory_writable(directory: Path) -> bool:
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe_path = directory / ".write_test"
        probe_path.write_text("", encoding="utf-8")
        probe_path.unlink()
        return True
    except OSError:
        return False


def _get_databricks_store() -> FileDecisionStore:
    """Databricks側の判断保存先への差し替え口（本フェーズでは未実装）。

    本番化時にここへ実際の保存処理（例: Delta テーブルへのINSERT）を実装する。
    """
    raise DecisionStorageUnavailableError(
        "Databricksへの判断保存は未実装のため、ファイルストレージへフォールバックします。"
    )


def get_decision_store(path: Optional[Path] = None) -> DecisionStore:
    """設定されたデータモードと書き込み可否に応じて判断ストレージを取得する。

    優先順位: Databricks（未実装のため常にフォールバック） → ファイル → インメモリ。
    書き込み先が読み取り専用等で使えない場合も例外を送出せず、インメモリへ
    安全にフォールバックする。
    """
    resolved_path = path if path is not None else DEFAULT_DECISIONS_PATH

    configured_mode = resolve_data_mode()
    if configured_mode == DATA_MODE_DATABRICKS:
        try:
            return _get_databricks_store()
        except DecisionStorageUnavailableError as exc:
            logger.warning(str(exc))

    if _is_directory_writable(resolved_path.parent):
        return FileDecisionStore(resolved_path)

    logger.warning(
        "判断保存先 %s へ書き込めないため、インメモリストレージへフォールバックします"
        "（アプリ再起動で判断が失われます）。",
        resolved_path.parent,
    )
    return _get_shared_in_memory_store()
