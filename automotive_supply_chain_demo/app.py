"""
自動車業界向け グローバル・サプライチェーン可視化とデータ共有 デモアプリ

Databricks Apps 上での実行を想定した Streamlit アプリケーション。
- AI チャット（Databricks FMAPI / RAG的挙動シミュレーション）
- ダッシュボード（地図・グラフによるサプライチェーン可視化）
- リスクシナリオ分析（地政学リスク・自然災害の影響シミュレーション）
- データ管理（サプライヤー／在庫の CRUD 管理画面）
- 使い方ガイド
"""

import streamlit as st

from src import chat_store, config, db, llm, risk_scenarios, visualizations as viz

st.set_page_config(
    page_title="自動車サプライチェーン可視化デモ",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────
# カスタム CSS（Material Design ライクな配色）
# ──────────────────────────────────────────────

st.markdown(f"""
<style>
    .stApp {{
        background-color: {config.COLOR_BG};
    }}
    .scm-badge {{
        display: inline-block;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-bottom: 8px;
    }}
    .scm-badge-live {{
        background-color: rgba(52,168,83,0.12);
        color: {config.COLOR_GREEN};
        border: 1px solid {config.COLOR_GREEN};
    }}
    .scm-badge-demo {{
        background-color: rgba(251,188,5,0.15);
        color: #B06D00;
        border: 1px solid {config.COLOR_YELLOW};
    }}
    .scm-kpi {{
        background-color: {config.COLOR_SURFACE};
        border: 1px solid {config.COLOR_BORDER};
        border-radius: 12px;
        padding: 14px 18px;
    }}
    section[data-testid="stSidebar"] .stButton button {{
        text-align: left;
        border-radius: 8px;
    }}
    div[data-testid="stChatMessage"] {{
        border-radius: 12px;
    }}
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────
# データロード（キャッシュせず、CRUD の即時反映を優先。データ規模は小さいため許容）
# ──────────────────────────────────────────────

def load_all_tables():
    return {
        "suppliers": db.get_suppliers(),
        "ports": db.get_ports(),
        "plants": db.get_assembly_plants(),
        "vehicle_models": db.get_vehicle_models(),
        "routes": db.get_logistics_routes(),
        "comp_map": db.get_vehicle_component_map(),
        "inventory": db.get_inventory(),
    }


# ──────────────────────────────────────────────
# サイドバー: ナビゲーション + モデル選択 + チャット履歴
# ──────────────────────────────────────────────

chat_store.init_chat_state()

_nav_override = st.session_state.pop("_nav_override", None)
if _nav_override:
    st.session_state["nav_page"] = _nav_override

with st.sidebar:
    st.markdown("### 🚗 SupplyChain Copilot")
    if db.is_demo_mode():
        st.markdown('<span class="scm-badge scm-badge-demo">● ローカルデモモード（SQLite）</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="scm-badge scm-badge-live">● Databricks 接続中（Unity Catalog）</span>', unsafe_allow_html=True)

    page = st.radio(
        "ナビゲーション",
        ["💬 AIチャット", "📊 ダッシュボード", "🚨 リスクシナリオ分析", "🗂️ データ管理", "📖 使い方ガイド"],
        label_visibility="collapsed",
        key="nav_page",
    )

    st.divider()
    st.markdown("**🧠 使用する LLM エンドポイント**")
    selected_model = st.selectbox(
        "Databricks FMAPI モデル",
        config.MODEL_ENDPOINTS,
        index=0,
        label_visibility="collapsed",
        help="Databricks Foundation Model API（Serving Endpoints）で提供されるモデルを選択します",
    )

    if page == "💬 AIチャット":
        st.divider()
        if st.button("➕ 新規チャット", use_container_width=True):
            chat_store.create_new_thread()
            st.rerun()

        st.markdown("**チャット履歴**")
        threads = chat_store.get_threads()
        active_id = chat_store.get_active_thread_id()
        # 新しい順に表示
        for tid in reversed(list(threads.keys())):
            thread = threads[tid]
            col1, col2 = st.columns([5, 1])
            with col1:
                btn_type = "primary" if tid == active_id else "secondary"
                if st.button(thread["title"], key=f"thread_{tid}", use_container_width=True, type=btn_type):
                    chat_store.set_active_thread(tid)
                    st.rerun()
            with col2:
                if st.button("🗑", key=f"del_{tid}", help="このチャットを削除"):
                    chat_store.delete_thread(tid)
                    st.rerun()


# ──────────────────────────────────────────────
# ページ: AI チャット
# ──────────────────────────────────────────────

def render_chat_page():
    st.title("💬 サプライチェーン AI アナリスト")
    st.caption(
        "Unity Catalog 上のサプライヤー・物流・在庫データを参照しながら、"
        "地政学リスクや部材遅延について質問に答えます（RAG的挙動のシミュレーション）。"
    )

    thread = chat_store.get_active_thread()

    for msg in thread["messages"]:
        with st.chat_message(msg["role"], avatar="🧑‍💼" if msg["role"] == "user" else "🚗"):
            st.markdown(msg["content"])
            if msg.get("context"):
                with st.expander("🔎 参照データ（Unity Catalogから取得）"):
                    st.markdown(msg["context"])

    if not thread["messages"]:
        st.info(
            "💡 質問例：\n"
            "- スエズ運河の停滞によるエンジン部品の遅延リスクは？\n"
            "- 台湾の半導体サプライヤーが操業停止した場合、どの車種に影響しますか？\n"
            "- タイヤ供給の代替サプライヤーを教えてください\n"
            "- Scope3排出量が最も多い部品カテゴリはどれですか？"
        )

    pending = st.session_state.pop("pending_question", None)
    user_input = st.chat_input("サプライチェーンについて質問してください…")
    question = pending or user_input

    if question:
        chat_store.add_message("user", question)
        with st.chat_message("user", avatar="🧑‍💼"):
            st.markdown(question)
        with st.chat_message("assistant", avatar="🚗"):
            with st.spinner(f"{selected_model} が分析中…"):
                answer, context_md = llm.chat_completion(selected_model, thread["messages"], question)
            st.markdown(answer)
            with st.expander("🔎 参照データ（Unity Catalogから取得）"):
                st.markdown(context_md)
        chat_store.add_message("assistant", answer, context=context_md)
        st.rerun()


# ──────────────────────────────────────────────
# ページ: ダッシュボード
# ──────────────────────────────────────────────

def render_dashboard_page(tables):
    st.title("📊 サプライチェーン ダッシュボード")

    suppliers, ports, plants = tables["suppliers"], tables["ports"], tables["plants"]
    routes, comp_map = tables["routes"], tables["comp_map"]

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown('<div class="scm-kpi">', unsafe_allow_html=True)
        st.metric("サプライヤー拠点数", f"{len(suppliers)}")
        st.markdown('</div>', unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="scm-kpi">', unsafe_allow_html=True)
        st.metric("物流ルート数", f"{len(routes)}")
        st.markdown('</div>', unsafe_allow_html=True)
    with c3:
        high_risk = int((suppliers["risk_level"] == "High").sum())
        st.markdown('<div class="scm-kpi">', unsafe_allow_html=True)
        st.metric("高リスク拠点数", f"{high_risk}", delta=None)
        st.markdown('</div>', unsafe_allow_html=True)
    with c4:
        total_co2 = routes["carbon_emissions_scope3_kg"].sum()
        st.markdown('<div class="scm-kpi">', unsafe_allow_html=True)
        st.metric("合計 Scope3 CO2排出量", f"{total_co2:,.0f} kg")
        st.markdown('</div>', unsafe_allow_html=True)

    st.write("")
    st.plotly_chart(viz.supply_chain_map(suppliers, ports, plants, routes), use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(viz.risk_by_region_bar(suppliers), use_container_width=True)
    with col2:
        st.plotly_chart(viz.emissions_by_category_bar(routes, suppliers), use_container_width=True)

    st.plotly_chart(viz.supply_flow_sankey(comp_map, suppliers), use_container_width=True)


# ──────────────────────────────────────────────
# ページ: リスクシナリオ分析
# ──────────────────────────────────────────────

def render_risk_page(tables):
    st.title("🚨 リスクシナリオ分析")
    st.caption("地政学リスクや自然災害の発生を想定し、影響を受けるサプライヤー・車種・代替候補を特定します。")

    suppliers, routes, comp_map, inventory = (
        tables["suppliers"], tables["routes"], tables["comp_map"], tables["inventory"]
    )
    ports, plants = tables["ports"], tables["plants"]

    scenario_key = st.selectbox(
        "シナリオを選択",
        list(risk_scenarios.SCENARIOS.keys()),
        format_func=lambda k: risk_scenarios.SCENARIOS[k]["label"],
    )
    scenario = risk_scenarios.SCENARIOS[scenario_key]
    st.info(scenario["description"])

    result = risk_scenarios.get_impacted_data(scenario_key, suppliers, routes, comp_map, inventory)

    st.plotly_chart(
        viz.supply_chain_map(suppliers, ports, plants, routes,
                              highlighted_supplier_ids=result["impacted_supplier_ids"]),
        use_container_width=True,
    )

    m1, m2, m3 = st.columns(3)
    m1.metric("影響を受けるサプライヤー数", len(result["impacted_suppliers"]))
    m2.metric("影響を受ける車種数", result["impacted_models"]["model_name"].nunique() if not result["impacted_models"].empty else 0)
    m3.metric("代替サプライヤー候補数", len(result["alt_suppliers"]))

    tab1, tab2, tab3, tab4 = st.tabs(["影響サプライヤー", "影響車種", "影響在庫", "代替サプライヤー候補"])
    with tab1:
        st.dataframe(result["impacted_suppliers"], use_container_width=True, hide_index=True)
    with tab2:
        st.dataframe(result["impacted_models"], use_container_width=True, hide_index=True)
    with tab3:
        st.dataframe(result["impacted_inventory"], use_container_width=True, hide_index=True)
    with tab4:
        st.dataframe(result["alt_suppliers"], use_container_width=True, hide_index=True)

    st.divider()
    if st.button("🤖 AIに詳細な代替案・提言を聞く", type="primary"):
        chat_store.create_new_thread()
        st.session_state["pending_question"] = scenario["question"]
        st.session_state["_nav_override"] = "💬 AIチャット"
        st.rerun()


# ──────────────────────────────────────────────
# ページ: データ管理（CRUD）
# ──────────────────────────────────────────────

def render_data_management_page(tables):
    st.title("🗂️ データ管理（サプライヤー / 在庫）")
    st.caption("Unity Catalog 上の Delta テーブルに対して、挿入・更新・削除を行うことができます。")

    tab_inv, tab_sup = st.tabs(["📦 在庫管理", "🏭 サプライヤー管理"])

    # ---------- 在庫管理 ----------
    with tab_inv:
        inventory = tables["inventory"]
        suppliers = tables["suppliers"]
        st.dataframe(inventory, use_container_width=True, hide_index=True)

        with st.expander("➕ 新規在庫を追加"):
            with st.form("add_inventory_form", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    new_id = st.text_input("在庫ID（例: INV9999）")
                    supplier_id = st.selectbox(
                        "サプライヤー",
                        suppliers["supplier_id"],
                        format_func=lambda sid: f"{sid} - {suppliers.set_index('supplier_id').loc[sid, 'supplier_name']}",
                    )
                    component_name = st.text_input("部品名")
                    warehouse_location = st.selectbox("倉庫拠点", db.sample_data.WAREHOUSE_LOCATIONS)
                with col2:
                    qty = st.number_input("在庫数量", min_value=0, value=1000, step=100)
                    reorder_point = st.number_input("発注点", min_value=0, value=200, step=50)
                    unit_cost = st.number_input("単価（USD）", min_value=0.0, value=10.0, step=0.5)
                submitted = st.form_submit_button("追加する", type="primary")
                if submitted:
                    if not new_id:
                        st.error("在庫IDを入力してください")
                    else:
                        sup_row = suppliers.set_index("supplier_id").loc[supplier_id]
                        db.insert_inventory_item({
                            "inventory_id": new_id,
                            "supplier_id": supplier_id,
                            "supplier_name": sup_row["supplier_name"],
                            "component_category": sup_row["component_category"],
                            "component_name": component_name or f"{sup_row['component_category']} - 新規",
                            "warehouse_location": warehouse_location,
                            "quantity_on_hand": int(qty),
                            "reorder_point": int(reorder_point),
                            "unit_cost_usd": float(unit_cost),
                            "last_updated": st.session_state.get("_today", "2026-07-02"),
                        })
                        st.success(f"在庫 {new_id} を追加しました")
                        st.rerun()

        with st.expander("✏️ 在庫を更新"):
            if not inventory.empty:
                target_id = st.selectbox("更新対象の在庫ID", inventory["inventory_id"], key="upd_inv_id")
                row = inventory.set_index("inventory_id").loc[target_id]
                with st.form("update_inventory_form"):
                    qty = st.number_input("在庫数量", min_value=0, value=int(row["quantity_on_hand"]), step=100)
                    reorder_point = st.number_input("発注点", min_value=0, value=int(row["reorder_point"]), step=50)
                    unit_cost = st.number_input("単価（USD）", min_value=0.0, value=float(row["unit_cost_usd"]), step=0.5)
                    submitted = st.form_submit_button("更新する", type="primary")
                    if submitted:
                        db.update_inventory_item(target_id, {
                            "quantity_on_hand": int(qty),
                            "reorder_point": int(reorder_point),
                            "unit_cost_usd": float(unit_cost),
                        })
                        st.success(f"在庫 {target_id} を更新しました")
                        st.rerun()

        with st.expander("🗑 在庫を削除"):
            if not inventory.empty:
                del_id = st.selectbox("削除対象の在庫ID", inventory["inventory_id"], key="del_inv_id")
                if st.button("この在庫を削除する", type="secondary"):
                    db.delete_inventory_item(del_id)
                    st.success(f"在庫 {del_id} を削除しました")
                    st.rerun()

    # ---------- サプライヤー管理 ----------
    with tab_sup:
        suppliers = tables["suppliers"]
        st.dataframe(suppliers, use_container_width=True, hide_index=True)

        with st.expander("➕ 新規サプライヤーを追加"):
            with st.form("add_supplier_form", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    new_id = st.text_input("サプライヤーID（例: SUP999）")
                    name = st.text_input("サプライヤー名")
                    tier = st.selectbox("Tier", ["Tier1", "Tier2"])
                    country = st.text_input("国")
                    region = st.selectbox("地域", ["APAC", "EMEA", "NA", "LATAM"])
                with col2:
                    city = st.text_input("都市")
                    lat = st.number_input("緯度", value=0.0, format="%.4f")
                    lon = st.number_input("経度", value=0.0, format="%.4f")
                    category = st.text_input("部品カテゴリ")
                    risk_score = st.slider("リスクスコア", 0, 100, 30)
                submitted = st.form_submit_button("追加する", type="primary")
                if submitted:
                    if not new_id or not name:
                        st.error("サプライヤーIDと名前は必須です")
                    else:
                        risk_level = "High" if risk_score >= 65 else ("Medium" if risk_score >= 35 else "Low")
                        db.insert_supplier({
                            "supplier_id": new_id,
                            "supplier_name": name,
                            "tier": tier,
                            "country": country,
                            "region": region,
                            "city": city,
                            "lat": lat,
                            "lon": lon,
                            "component_category": category,
                            "risk_score": int(risk_score),
                            "risk_level": risk_level,
                        })
                        st.success(f"サプライヤー {new_id} を追加しました")
                        st.rerun()

        with st.expander("✏️ サプライヤーを更新"):
            if not suppliers.empty:
                target_id = st.selectbox("更新対象のサプライヤーID", suppliers["supplier_id"], key="upd_sup_id")
                row = suppliers.set_index("supplier_id").loc[target_id]
                with st.form("update_supplier_form"):
                    risk_score = st.slider("リスクスコア", 0, 100, int(row["risk_score"]))
                    category = st.text_input("部品カテゴリ", value=row["component_category"])
                    submitted = st.form_submit_button("更新する", type="primary")
                    if submitted:
                        risk_level = "High" if risk_score >= 65 else ("Medium" if risk_score >= 35 else "Low")
                        db.update_supplier(target_id, {
                            "risk_score": int(risk_score),
                            "risk_level": risk_level,
                            "component_category": category,
                        })
                        st.success(f"サプライヤー {target_id} を更新しました")
                        st.rerun()

        with st.expander("🗑 サプライヤーを削除"):
            if not suppliers.empty:
                del_id = st.selectbox("削除対象のサプライヤーID", suppliers["supplier_id"], key="del_sup_id")
                if st.button("このサプライヤーを削除する", type="secondary"):
                    db.delete_supplier(del_id)
                    st.success(f"サプライヤー {del_id} を削除しました")
                    st.rerun()


# ──────────────────────────────────────────────
# ページ: 使い方ガイド
# ──────────────────────────────────────────────

def render_help_page():
    st.title("📖 使い方ガイド")

    st.markdown("""
## デモのシナリオ

本デモは、自動車メーカー（OEM）のサプライチェーン管理部門が、**地政学リスクや自然災害発生時に
どの車種の生産へ影響が及ぶかを即座に特定し、AIが代替サプライヤーを提案する** ユースケースを
Databricks 上で再現したものです。

Unity Catalog 上の Delta テーブル（UniForm 有効化により Apache Iceberg クライアントからも読み取り可能）に
部品メーカー・港湾・物流ルート・在庫データを格納し、Databricks FMAPI（Foundation Model API）を
使ったチャット機能でデータに基づいた分析・提案を行います。

## 操作手順

1. **📊 ダッシュボード** で、世界地図上のサプライヤー・港湾・組立工場・物流ルートの全体像を確認します。
2. **🚨 リスクシナリオ分析** で、スエズ運河の停滞や台湾地震などのシナリオを選択し、
   影響を受けるサプライヤー・車種・在庫・代替候補を確認します。
3. 分析結果画面の **「🤖 AIに詳細な代替案・提言を聞く」** ボタンから、AIチャットに質問を引き継ぎ、
   より詳細な提案を得ることができます。
4. **💬 AIチャット** では、サイドバーで LLM エンドポイント（Llama 3.1 70B / Mixtral 8x7B 等）を選択し、
   自由に質問できます。過去のチャットはサイドバーにスレッドとして保持されます。
5. **🗂️ データ管理** で、サプライヤー情報や在庫データを追加・更新・削除できます（Delta テーブルへ即時反映）。

## 質問例

- 「スエズ運河の停滞によるエンジン部品の遅延リスクは？」
- 「台湾の半導体サプライヤーが操業停止した場合、どの車種に影響しますか？」
- 「タイヤ供給の代替サプライヤーを教えてください」
- 「Scope3排出量が最も多い部品カテゴリはどれですか？」

## データについて

- サプライヤー・港湾・組立工場・物流ルート・在庫はすべてサンプルデータです（`data_setup.py` で生成）。
- 実運用ワークスペースに接続していない場合は、ローカル SQLite によるデモモードで動作します
  （サイドバーの「ローカルデモモード」バッジで確認できます）。
""")


# ──────────────────────────────────────────────
# メイン
# ──────────────────────────────────────────────

active_page = page

tables = load_all_tables()

if active_page == "💬 AIチャット":
    render_chat_page()
elif active_page == "📊 ダッシュボード":
    render_dashboard_page(tables)
elif active_page == "🚨 リスクシナリオ分析":
    render_risk_page(tables)
elif active_page == "🗂️ データ管理":
    render_data_management_page(tables)
elif active_page == "📖 使い方ガイド":
    render_help_page()
