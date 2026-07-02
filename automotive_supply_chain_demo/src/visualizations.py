"""
Plotly を用いたサプライチェーン可視化コンポーネント
Google Material Design ライクなカラーパレット（src/config.py）を使用する
"""

import pandas as pd
import plotly.graph_objects as go

from . import config

# 簡略化した大陸の輪郭（lon, lat）。Plotly の Scattergeo は本来 showland=True 等を
# 指定すると外部CDN（cdn.plot.ly）から地形データ（topojson）を取得するが、
# 社内ネットワークなど外部インターネットアクセスが制限された Databricks 環境でも
# 確実に描画できるよう、簡略化したポリゴンをアプリ内に直接埋め込んで自前描画する。
_CONTINENT_OUTLINES = {
    "北米": [(-170, 15), (-155, 60), (-130, 70), (-95, 72), (-70, 60), (-52, 48),
              (-65, 25), (-97, 18), (-117, 20), (-170, 15)],
    "南米": [(-82, 8), (-60, 12), (-34, -5), (-40, -23), (-58, -55), (-75, -45),
              (-82, -18), (-82, 8)],
    "欧州": [(-11, 36), (-11, 60), (20, 71), (40, 66), (30, 45), (18, 40), (-5, 36), (-11, 36)],
    "アフリカ": [(-18, 15), (10, 37), (33, 32), (52, 12), (42, -25), (18, -35),
                (12, -5), (-18, 15)],
    "アジア": [(28, 42), (60, 55), (90, 76), (140, 73), (150, 45), (140, 35),
              (120, 22), (95, 8), (75, 8), (60, 25), (45, 30), (28, 42)],
    "オセアニア": [(112, -22), (130, -12), (153, -28), (145, -39), (117, -35), (112, -22)],
}


def _add_continent_shapes(fig: go.Figure):
    for coords in _CONTINENT_OUTLINES.values():
        lons = [c[0] for c in coords]
        lats = [c[1] for c in coords]
        fig.add_trace(go.Scattergeo(
            lon=lons, lat=lats, mode="lines", fill="toself",
            fillcolor="#F1F3F4", line=dict(color="#E3E5E8", width=1),
            showlegend=False, hoverinfo="skip",
        ))


def _base_geo_layout(fig: go.Figure, title: str):
    fig.update_layout(
        title=dict(text=title, font=dict(size=18, color=config.COLOR_TEXT)),
        geo=dict(
            projection_type="natural earth",
            # showland/showcountries 等は使わない（外部CDNからのtopojson取得が必要なため）。
            # 大陸の輪郭は _add_continent_shapes() で自前描画している。
            showland=False,
            showocean=False,
            showcountries=False,
            showframe=True,
            framecolor=config.COLOR_BORDER,
            showcoastlines=False,
            bgcolor="#E8F0FE",
            lonaxis=dict(showgrid=True, gridcolor="#EEF1F4", gridwidth=0.5),
            lataxis=dict(showgrid=True, gridcolor="#EEF1F4", gridwidth=0.5),
        ),
        paper_bgcolor=config.COLOR_BG,
        plot_bgcolor=config.COLOR_BG,
        margin=dict(l=0, r=0, t=50, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=-0.05, x=0.5, xanchor="center"),
        height=560,
    )
    return fig


def supply_chain_map(
    suppliers: pd.DataFrame,
    ports: pd.DataFrame,
    plants: pd.DataFrame,
    routes: pd.DataFrame,
    highlighted_supplier_ids: set | None = None,
) -> go.Figure:
    """サプライヤー・港湾・組立工場をノードとし、物流ルートをラインで描画する世界地図"""
    highlighted_supplier_ids = highlighted_supplier_ids or set()
    fig = go.Figure()

    _add_continent_shapes(fig)

    # ルート（線）
    for _, r in routes.iterrows():
        is_highlighted = r["supplier_id"] in highlighted_supplier_ids
        line_color = config.COLOR_RED if is_highlighted else "rgba(95,99,104,0.25)"
        line_width = 2.2 if is_highlighted else 0.6
        fig.add_trace(go.Scattergeo(
            lon=[r["origin_lon"], r["dest_lon"]],
            lat=[r["origin_lat"], r["dest_lat"]],
            mode="lines",
            line=dict(width=line_width, color=line_color),
            opacity=0.9 if is_highlighted else 0.5,
            hoverinfo="skip",
            showlegend=False,
        ))

    # サプライヤー（Tier2 / Tier1）
    for tier, color in [("Tier2", config.COLOR_YELLOW), ("Tier1", config.COLOR_BLUE)]:
        sub = suppliers[suppliers["tier"] == tier]
        marker_line = [
            config.COLOR_RED if sid in highlighted_supplier_ids else "white"
            for sid in sub["supplier_id"]
        ]
        fig.add_trace(go.Scattergeo(
            lon=sub["lon"], lat=sub["lat"],
            mode="markers",
            name=f"{tier} サプライヤー",
            marker=dict(size=10, color=color, line=dict(width=1.5, color=marker_line), symbol="circle"),
            text=sub["supplier_name"] + "（" + sub["component_category"] + "）",
            hovertemplate="%{text}<extra></extra>",
        ))

    # 港湾（チョークポイントは強調）
    fig.add_trace(go.Scattergeo(
        lon=ports["lon"], lat=ports["lat"],
        mode="markers",
        name="港湾 / チョークポイント",
        marker=dict(
            size=[16 if c else 9 for c in ports["is_chokepoint"]],
            color=config.COLOR_GREEN,
            symbol="diamond",
            line=dict(width=1.5, color="white"),
        ),
        text=ports["port_name"] + "（混雑度: " + ports["congestion_level"] + "）",
        hovertemplate="%{text}<extra></extra>",
    ))

    # 組立工場
    fig.add_trace(go.Scattergeo(
        lon=plants["lon"], lat=plants["lat"],
        mode="markers",
        name="完成車組立工場",
        marker=dict(size=14, color=config.COLOR_RED, symbol="square", line=dict(width=1.5, color="white")),
        text=plants["plant_name"] + "（" + plants["oem"] + "）",
        hovertemplate="%{text}<extra></extra>",
    ))

    return _base_geo_layout(fig, "🌍 グローバル・サプライチェーン マップ")


def emissions_by_category_bar(routes: pd.DataFrame, suppliers: pd.DataFrame) -> go.Figure:
    merged = routes.merge(
        suppliers[["supplier_id", "component_category"]], on="supplier_id", how="left"
    )
    agg = merged.groupby("component_category", as_index=False)["carbon_emissions_scope3_kg"].sum()
    agg = agg.sort_values("carbon_emissions_scope3_kg", ascending=True)

    fig = go.Figure(go.Bar(
        x=agg["carbon_emissions_scope3_kg"],
        y=agg["component_category"],
        orientation="h",
        marker=dict(color=config.COLOR_BLUE),
    ))
    fig.update_layout(
        title="部品カテゴリ別 Scope3 輸送CO2排出量（kg）",
        paper_bgcolor=config.COLOR_BG,
        plot_bgcolor=config.COLOR_BG,
        margin=dict(l=10, r=10, t=50, b=10),
        height=420,
        font=dict(color=config.COLOR_TEXT),
        xaxis=dict(gridcolor=config.COLOR_BORDER),
    )
    return fig


def risk_by_region_bar(suppliers: pd.DataFrame) -> go.Figure:
    agg = suppliers.groupby("region", as_index=False)["risk_score"].mean().sort_values("risk_score")
    fig = go.Figure(go.Bar(
        x=agg["region"], y=agg["risk_score"],
        marker=dict(color=[config.COLOR_GREEN if v < 40 else config.COLOR_YELLOW if v < 65 else config.COLOR_RED
                            for v in agg["risk_score"]]),
    ))
    fig.update_layout(
        title="地域別 平均サプライヤー・リスクスコア",
        paper_bgcolor=config.COLOR_BG,
        plot_bgcolor=config.COLOR_BG,
        margin=dict(l=10, r=10, t=50, b=10),
        height=380,
        font=dict(color=config.COLOR_TEXT),
        yaxis=dict(gridcolor=config.COLOR_BORDER, range=[0, 100]),
    )
    return fig


def supply_flow_sankey(comp_map: pd.DataFrame, suppliers: pd.DataFrame) -> go.Figure:
    """Tier2/Tier1 サプライヤー → 部品カテゴリ → OEM の流れを Sankey で可視化"""
    merged = comp_map.merge(
        suppliers[["supplier_id", "tier"]], on="supplier_id", how="left"
    )

    tiers = sorted(merged["tier"].dropna().unique())
    categories = sorted(merged["component_category"].dropna().unique())
    oems = sorted(merged["oem"].dropna().unique())

    labels = list(tiers) + list(categories) + list(oems)
    label_index = {label: i for i, label in enumerate(labels)}

    node_colors = (
        [config.COLOR_YELLOW if t == "Tier2" else config.COLOR_BLUE for t in tiers]
        + [config.COLOR_GREEN for _ in categories]
        + [config.COLOR_RED for _ in oems]
    )

    link_source, link_target, link_value = [], [], []

    tier_cat = merged.groupby(["tier", "component_category"]).size().reset_index(name="count")
    for _, row in tier_cat.iterrows():
        link_source.append(label_index[row["tier"]])
        link_target.append(label_index[row["component_category"]])
        link_value.append(row["count"])

    cat_oem = merged.groupby(["component_category", "oem"]).size().reset_index(name="count")
    for _, row in cat_oem.iterrows():
        link_source.append(label_index[row["component_category"]])
        link_target.append(label_index[row["oem"]])
        link_value.append(row["count"])

    fig = go.Figure(go.Sankey(
        node=dict(
            label=labels,
            color=node_colors,
            pad=14,
            thickness=16,
            line=dict(color="white", width=0.5),
        ),
        link=dict(source=link_source, target=link_target, value=link_value,
                  color="rgba(66,133,244,0.25)"),
    ))
    fig.update_layout(
        title="サプライヤー階層 → 部品カテゴリ → OEM の供給フロー",
        paper_bgcolor=config.COLOR_BG,
        margin=dict(l=10, r=10, t=50, b=10),
        height=480,
        font=dict(color=config.COLOR_TEXT),
    )
    return fig
