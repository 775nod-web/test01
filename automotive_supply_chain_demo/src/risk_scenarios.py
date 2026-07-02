"""
地政学リスク・自然災害シナリオの定義と影響分析ロジック

各シナリオは、影響を受ける拠点を絞り込むためのフィルタ条件を持つ。
「リスク分析」タブと「チャット」タブの双方から利用する。
"""

import pandas as pd

SCENARIOS = {
    "suez_blockage": {
        "label": "🚢 スエズ運河の停滞（座礁事故を想定）",
        "description": "スエズ運河を経由する海上輸送ルートが数週間にわたり停止するシナリオ。",
        "question": "スエズ運河の停滞によるエンジン部品や電子部品の遅延リスクは？代替サプライヤーも提案してください。",
        "filter": lambda routes: routes["via_port_id"] == "PRT007",
    },
    "taiwan_earthquake": {
        "label": "🌏 台湾での大規模地震（半導体供給網の寸断）",
        "description": "台湾の半導体サプライヤー拠点が操業停止するシナリオ。",
        "question": "台湾の地震により半導体サプライヤーが操業停止した場合、どの車種の生産に影響しますか？代替の半導体サプライヤーを提案してください。",
        "filter": lambda routes, suppliers: suppliers["country"] == "Taiwan",
        "supplier_filter": True,
    },
    "japan_earthquake": {
        "label": "🗾 日本での大規模地震（Tier1部品供給の停止）",
        "description": "日本国内の主要 Tier1 サプライヤー（エンジン・トランスミッション等）が操業停止するシナリオ。",
        "question": "日本の地震によりエンジン・トランスミッション部品の供給が止まった場合の影響と代替サプライヤーを教えてください。",
        "filter": lambda routes, suppliers: suppliers["country"] == "Japan",
        "supplier_filter": True,
    },
    "panama_drought": {
        "label": "🌊 パナマ運河の水位低下（渇水による通航制限）",
        "description": "パナマ運河の通航隻数が制限され、北米向け輸送が遅延するシナリオ。",
        "question": "パナマ運河の渇水による通航制限が北米工場向けの部品供給に与える影響は？",
        "filter": lambda routes: routes["via_port_id"] == "PRT012",
    },
    "malacca_congestion": {
        "label": "⚓ マラッカ海峡の混雑（アジア域内輸送の遅延）",
        "description": "マラッカ海峡の船舶渋滞により、東南アジア発の輸送が遅延するシナリオ。",
        "question": "マラッカ海峡の混雑がタイヤ・ゴム部品の供給に与える影響と対応策は？",
        "filter": lambda routes: routes["via_port_id"] == "PRT013",
    },
}


def get_impacted_data(scenario_key: str, suppliers: pd.DataFrame, routes: pd.DataFrame,
                       comp_map: pd.DataFrame, inventory: pd.DataFrame):
    """シナリオに応じて影響を受けるサプライヤー・ルート・車種・在庫を抽出する"""
    scenario = SCENARIOS[scenario_key]

    if scenario.get("supplier_filter"):
        sup_mask = scenario["filter"](routes, suppliers)
        impacted_suppliers = suppliers[sup_mask]
        impacted_supplier_ids = set(impacted_suppliers["supplier_id"])
        impacted_routes = routes[routes["supplier_id"].isin(impacted_supplier_ids)]
    else:
        route_mask = scenario["filter"](routes)
        impacted_routes = routes[route_mask]
        impacted_supplier_ids = set(impacted_routes["supplier_id"])
        impacted_suppliers = suppliers[suppliers["supplier_id"].isin(impacted_supplier_ids)]

    impacted_models = comp_map[comp_map["supplier_id"].isin(impacted_supplier_ids)]
    impacted_inventory = inventory[inventory["supplier_id"].isin(impacted_supplier_ids)]

    categories = set(impacted_suppliers["component_category"]) if not impacted_suppliers.empty else set()
    alt_suppliers = suppliers[
        suppliers["component_category"].isin(categories)
        & (~suppliers["supplier_id"].isin(impacted_supplier_ids))
        & (suppliers["risk_score"] < 45)
    ].sort_values("risk_score").head(8)

    return {
        "impacted_suppliers": impacted_suppliers,
        "impacted_routes": impacted_routes,
        "impacted_models": impacted_models,
        "impacted_inventory": impacted_inventory,
        "alt_suppliers": alt_suppliers,
        "impacted_supplier_ids": impacted_supplier_ids,
    }
