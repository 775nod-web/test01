"""判断保存先が書き込み不可（読み取り専用ファイルシステム等）の場合の
インメモリフォールバックを検証する。

Databricks Apps環境ではコンテナのファイルシステムが読み取り専用になる場合がある
ことを想定し、書き込み失敗時でも判断保存API自体は失敗させず、`persisted=False`
を返すことを確認する。
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from backend.services import decision_store as decision_store_module
from backend.services.decision_store import (
    STORAGE_MODE_FILE,
    STORAGE_MODE_MEMORY,
    FileDecisionStore,
    get_decision_store,
)


@pytest.fixture(autouse=True)
def reset_shared_in_memory_store():
    """テスト間でインメモリのフォールバック内容が漏れないようにする。"""
    decision_store_module._shared_in_memory_store = None
    yield
    decision_store_module._shared_in_memory_store = None


def test_writable_directory_uses_file_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABRICKS_SERVER_HOSTNAME", raising=False)
    monkeypatch.delenv("DATABRICKS_HTTP_PATH", raising=False)
    monkeypatch.delenv("DATABRICKS_TOKEN", raising=False)

    store = get_decision_store(path=tmp_path / "decisions.json")
    assert isinstance(store, FileDecisionStore)
    assert store.storage_mode == STORAGE_MODE_FILE
    assert store.persisted is True

    saved = store.save_decision({"customer_id": "C001", "decision": "approved"})
    assert saved["persisted"] is True


def test_read_only_directory_falls_back_to_in_memory_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DATABRICKS_SERVER_HOSTNAME", raising=False)
    monkeypatch.delenv("DATABRICKS_HTTP_PATH", raising=False)
    monkeypatch.delenv("DATABRICKS_TOKEN", raising=False)

    read_only_dir = tmp_path / "read_only"
    read_only_dir.mkdir()
    read_only_dir.chmod(stat.S_IREAD | stat.S_IEXEC)

    try:
        if os.access(read_only_dir, os.W_OK):
            pytest.skip("この実行環境ではroot権限のためディレクトリの書き込み制限が効かない")

        store = get_decision_store(path=read_only_dir / "decisions.json")
        assert store.storage_mode == STORAGE_MODE_MEMORY
        assert store.persisted is False

        saved = store.save_decision({"customer_id": "C001", "decision": "skipped"})
        assert saved["persisted"] is False
        assert store.list_decisions() == [saved]
    finally:
        read_only_dir.chmod(stat.S_IRWXU)


def test_unwritable_path_falls_back_to_in_memory_store_regardless_of_privileges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """chmodベースの読み取り専用はroot権限下では効かないため、親コンポーネントが
    ファイルであるパス（mkdirが構造的に失敗する）で、権限に依存せず検証する。"""
    monkeypatch.delenv("DATABRICKS_SERVER_HOSTNAME", raising=False)
    monkeypatch.delenv("DATABRICKS_HTTP_PATH", raising=False)
    monkeypatch.delenv("DATABRICKS_TOKEN", raising=False)

    blocking_file = tmp_path / "not_a_directory"
    blocking_file.write_text("", encoding="utf-8")
    impossible_path = blocking_file / "nested" / "decisions.json"

    store = get_decision_store(path=impossible_path)
    assert store.storage_mode == STORAGE_MODE_MEMORY
    assert store.persisted is False

    saved = store.save_decision({"customer_id": "C001", "decision": "modified"})
    assert saved["persisted"] is False


def test_in_memory_fallback_is_shared_across_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """書き込み不可と判定された後も、同一プロセス内では同じフォールバック
    ストアを使い続け、直前に保存した判断がlist_decisionsへ反映されること。"""
    monkeypatch.delenv("DATABRICKS_SERVER_HOSTNAME", raising=False)
    monkeypatch.delenv("DATABRICKS_HTTP_PATH", raising=False)
    monkeypatch.delenv("DATABRICKS_TOKEN", raising=False)

    blocking_file = tmp_path / "not_a_directory"
    blocking_file.write_text("", encoding="utf-8")
    path = blocking_file / "nested" / "decisions.json"

    first_call_store = get_decision_store(path=path)
    first_call_store.save_decision({"customer_id": "C001", "decision": "approved"})

    second_call_store = get_decision_store(path=path)
    assert second_call_store.list_decisions() != []
