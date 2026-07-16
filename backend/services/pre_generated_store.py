"""事前生成済みLLM回答（`pre_generated`）フィクスチャの読み込み。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

PRE_GENERATED_PATH = (
    Path(__file__).resolve().parent.parent.parent / "artifacts" / "pre_generated_recommendations.json"
)


def load_pre_generated_recommendation(
    customer_id: str, path: Optional[Path] = None
) -> Optional[dict]:
    """指定顧客の事前生成済み回答があれば返す。無ければNone。

    ファイル自体が存在しない場合もNoneを返し、ルールベースへフォールバックできるようにする。
    """
    resolved_path = path if path is not None else PRE_GENERATED_PATH
    if not resolved_path.exists():
        return None

    with resolved_path.open(encoding="utf-8") as f:
        data = json.load(f)

    return data.get("recommendations", {}).get(customer_id)
