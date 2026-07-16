"""社内ナレッジ文書（過去施策の説明・サービス情報・顧客対応方針）の読み込み。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

KNOWLEDGE_BASE_PATH = (
    Path(__file__).resolve().parent.parent.parent / "data" / "knowledge" / "knowledge_base.json"
)

# 過去施策のcampaign_type（data/campaigns.csv, artifacts/customer360.jsonで使われる値）と
# ナレッジ文書のdoc_idの対応表。
CAMPAIGN_TYPE_TO_DOC_ID = {
    "EC再訪促進メール": "kb-ec-revisit",
    "QR決済ポイント還元": "kb-qr-incentive",
    "カード利用特典案内": "kb-card-benefit",
    "複数サービス横断ポイント施策": "kb-cross-service",
}


def load_knowledge_docs(path: Optional[Path] = None) -> list[dict]:
    resolved_path = path if path is not None else KNOWLEDGE_BASE_PATH
    with resolved_path.open(encoding="utf-8") as f:
        return json.load(f)


def select_relevant_docs(docs: Optional[list[dict]] = None) -> list[dict]:
    """推奨アクション生成の候補となるナレッジ文書一式を返す。

    ナレッジベースは6件と少数のため、事前に絞り込まず全件を候補プールとして渡し、
    実際に根拠として使う文書の選択は生成方式（LLM／事前生成／ルールベース）側に委ねる。
    表示・APIで返す「参照元」は、候補プールではなく実際に引用した文書のみとする。
    """
    return docs if docs is not None else load_knowledge_docs()
