"""施策後の反応・利用再開のデモ用固定サンプルの読み込み。

Step 6「フィードバック概要」で、担当者の判断（実データ）とあわせて表示する。
ここで返す反応・利用再開の内容は固定サンプルであり、実際の顧客の反応ではない。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

SAMPLE_OUTCOMES_PATH = (
    Path(__file__).resolve().parent.parent.parent / "artifacts" / "sample_campaign_outcomes.json"
)


def load_sample_outcomes(path: Optional[Path] = None) -> list[dict]:
    """固定サンプルの施策結果一覧を返す。

    ファイルが存在しない場合は空リストを返し、フィードバック概要の取得自体は
    失敗させない（サンプル表示は無くても既存の判断集計は動作を続けられる）。
    """
    resolved_path = path if path is not None else SAMPLE_OUTCOMES_PATH
    if not resolved_path.exists():
        return []

    with resolved_path.open(encoding="utf-8") as f:
        data = json.load(f)

    return data.get("outcomes", [])
