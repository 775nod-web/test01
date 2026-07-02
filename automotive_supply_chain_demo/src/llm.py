"""
Databricks FMAPI（Foundation Model API）連携

- OpenAI 互換クライアントを使い、Serving Endpoints 経由でチャット補完を呼び出す
  参考: https://docs.databricks.com/en/machine-learning/foundation-models/index.html
- サプライチェーンのデータに基づいた RAG 的な挙動をシミュレートするため、
  質問文からキーワード（拠点名・部品カテゴリ・国名など）を抽出し、
  Unity Catalog 上のテーブルから関連行を検索して LLM のコンテキストに埋め込む。
  （本デモは簡易的なキーワードマッチによる検索であり、Databricks Vector Search
    などによる本格的なベクトル検索の代替として位置づけている）
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from . import config, db

SYSTEM_PROMPT = """あなたは自動車業界のグローバル・サプライチェーンを専門とするAIアナリストです。
Databricks Unity Catalog に格納されたサプライヤー・港湾・物流ルート・在庫・車種構成データを
参照しながら、地政学リスクや自然災害がサプライチェーンに与える影響を分析し、
代替サプライヤーの提案や具体的なアクションを、簡潔かつ実務的な日本語で回答してください。

回答時は以下を意識してください：
- 提供された「参照データ」に基づいて具体的に回答する（拠点名・数値を引用する）
- 影響を受ける車種・OEMを特定する
- 可能であれば代替サプライヤー（同一 component_category かつリスクスコアが低い拠点）を提案する
- 参照データに答えがない場合は、一般的な知見として回答しつつ、その旨を明示する
"""


@st.cache_resource
def _get_client(host: str, token: str):
    from openai import OpenAI
    return OpenAI(
        api_key=token,
        base_url=f"https://{host}/serving-endpoints",
    )


def is_llm_configured() -> bool:
    return bool(config.DATABRICKS_HOST and config.DATABRICKS_TOKEN)


# ──────────────────────────────────────────────
# 簡易 RAG: キーワード抽出 → テーブル検索 → コンテキスト構築
# ──────────────────────────────────────────────

# 日本語の通称 → 英語の正式名称（拠点名など）のエイリアス辞書
_ALIASES = {
    "スエズ運河": "スエズ運河",
    "パナマ運河": "パナマ運河",
    "マラッカ海峡": "マラッカ海峡",
    "台湾": "Taiwan",
    "中国": "China",
    "半導体": "半導体/ECU",
    "エンジン": "エンジン部品",
    "バッテリー": "バッテリー",
    "ブレーキ": "ブレーキシステム",
    "タイヤ": "タイヤ",
    "ワイヤーハーネス": "ワイヤーハーネス",
    "地震": "Japan",
    "日本": "Japan",
    "メキシコ": "Mexico",
    "ドイツ": "Germany",
    "港": "港",
}


def _extract_keywords(question: str) -> list[str]:
    hits = []
    for alias, normalized in _ALIASES.items():
        if alias in question:
            hits.append(normalized)
    return list(dict.fromkeys(hits))  # 重複除去（順序維持）


def retrieve_context(question: str) -> tuple[str, dict[str, pd.DataFrame]]:
    """質問文に関連するテーブル行を検索し、Markdown 化したコンテキストと生データを返す"""
    keywords = _extract_keywords(question)

    suppliers = db.get_suppliers()
    routes = db.get_logistics_routes()
    comp_map = db.get_vehicle_component_map()
    inventory = db.get_inventory()

    if not keywords:
        # キーワードが取れない場合は、リスクスコア上位のサプライヤーなど代表データを返す
        matched_suppliers = suppliers.sort_values("risk_score", ascending=False).head(5)
        matched_routes = routes[routes["via_chokepoint"] == True].head(5)  # noqa: E712
        affected_supplier_ids = set(matched_suppliers["supplier_id"]) | set(matched_routes["supplier_id"])
        matched_map = comp_map[comp_map["supplier_id"].isin(affected_supplier_ids)].head(5)
        matched_inventory = inventory[inventory["supplier_id"].isin(affected_supplier_ids)].head(5)
    else:
        sup_mask = pd.Series(False, index=suppliers.index)
        route_mask = pd.Series(False, index=routes.index)
        for kw in keywords:
            sup_mask |= (
                suppliers["country"].str.contains(kw, case=False, na=False)
                | suppliers["component_category"].str.contains(kw, case=False, na=False)
                | suppliers["supplier_name"].str.contains(kw, case=False, na=False)
            )
            route_mask |= (
                routes["via_port_name"].fillna("").str.contains(kw, case=False, na=False)
                | routes["supplier_name"].str.contains(kw, case=False, na=False)
            )

        matched_suppliers = suppliers[sup_mask].head(8)
        matched_routes = routes[route_mask].head(8)

        # 該当サプライヤーに紐づく在庫・影響車種も併せて取得
        affected_supplier_ids = set(matched_suppliers["supplier_id"]) | set(matched_routes["supplier_id"])
        matched_map = comp_map[comp_map["supplier_id"].isin(affected_supplier_ids)].head(8)
        matched_inventory = inventory[inventory["supplier_id"].isin(affected_supplier_ids)].head(8)

    # 代替サプライヤー候補（同カテゴリ・低リスク）
    categories = set(matched_suppliers["component_category"]) if not matched_suppliers.empty else set()
    alt_suppliers = suppliers[
        suppliers["component_category"].isin(categories)
        & (~suppliers["supplier_id"].isin(matched_suppliers["supplier_id"]))
        & (suppliers["risk_score"] < 40)
    ].sort_values("risk_score").head(5)

    parts = []
    if not matched_suppliers.empty:
        parts.append("### 関連サプライヤー\n" + matched_suppliers[
            ["supplier_id", "supplier_name", "tier", "country", "component_category", "risk_score", "risk_level"]
        ].to_markdown(index=False))
    if not matched_routes.empty:
        parts.append("### 関連物流ルート\n" + matched_routes[
            ["route_id", "supplier_name", "plant_name", "transport_mode", "via_port_name",
             "via_chokepoint", "transit_days", "carbon_emissions_scope3_kg"]
        ].to_markdown(index=False))
    if not matched_map.empty:
        parts.append("### 影響を受ける可能性のある車種\n" + matched_map[
            ["model_name", "oem", "component_category", "supplier_name", "criticality"]
        ].to_markdown(index=False))
    if not matched_inventory.empty:
        parts.append("### 関連在庫状況\n" + matched_inventory[
            ["inventory_id", "supplier_name", "component_name", "quantity_on_hand", "reorder_point", "warehouse_location"]
        ].to_markdown(index=False))
    if not alt_suppliers.empty:
        parts.append("### 代替サプライヤー候補（同カテゴリ・低リスク）\n" + alt_suppliers[
            ["supplier_id", "supplier_name", "country", "component_category", "risk_score"]
        ].to_markdown(index=False))

    context_md = "\n\n".join(parts) if parts else "（関連データが見つかりませんでした）"

    retrieved = {
        "suppliers": matched_suppliers,
        "routes": matched_routes,
        "vehicle_component_map": matched_map,
        "inventory": matched_inventory,
        "alt_suppliers": alt_suppliers,
    }
    return context_md, retrieved


def chat_completion(model: str, history: list[dict], question: str) -> tuple[str, str]:
    """
    質問に対して RAG 的にコンテキストを検索した上で FMAPI にリクエストする。
    戻り値: (回答テキスト, 参照データのMarkdown)
    """
    context_md, _ = retrieve_context(question)

    user_content = (
        f"## 参照データ（Unity Catalog より取得）\n{context_md}\n\n"
        f"## 質問\n{question}"
    )

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history[-8:]:  # 直近の履歴のみ（トークン節約）
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_content})

    if not is_llm_configured():
        return _mock_response(question, context_md), context_md

    try:
        client = _get_client(config.DATABRICKS_HOST, config.DATABRICKS_TOKEN)
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=1024,
            temperature=0.3,
        )
        answer = response.choices[0].message.content
        return answer, context_md
    except Exception as e:  # noqa: BLE001
        return f"⚠️ FMAPI 呼び出しでエラーが発生しました: {e}", context_md


def _mock_response(question: str, context_md: str) -> str:
    """Databricks 未接続時（ローカルデモモード）のモック回答"""
    return (
        "⚠️ これはローカルデモモードの模擬回答です（Databricks FMAPI 未接続）。\n\n"
        "実際の Databricks ワークスペースにデプロイすると、選択したモデルエンドポイント "
        "（例: `databricks-meta-llama-3-1-70b-instruct`）が以下の参照データを踏まえて "
        "具体的な分析・代替サプライヤー提案を生成します。\n\n"
        f"---\n**質問:** {question}\n\n**取得された参照データのプレビュー:**\n\n{context_md[:800]}"
    )
