import gradio as gr
import plotly.express as px
import pandas as pd

# ──────────────────────────────────────────────
# データ読み込み関数
# ──────────────────────────────────────────────

def load_kpi_data() -> pd.DataFrame:
    """
    Gold Layer の KPI テーブルを読み込んで pandas DataFrame に変換する。
    テーブルが存在しない場合は空の DataFrame を返す。
    """
    try:
        df = spark.table("interview_prep.gold_kpi_daily").toPandas()
        # event_date を datetime 型に変換してグラフの軸を正しく並べる
        df["event_date"] = pd.to_datetime(df["event_date"])
        return df
    except Exception as e:
        # テーブルが存在しない・権限エラーなどをまとめて捕捉
        print(f"[ERROR] gold_kpi_daily の読み込みに失敗しました: {e}")
        return pd.DataFrame()


def load_churn_data() -> pd.DataFrame:
    """
    Gold Layer のチャーン特徴量テーブルを読み込んで pandas DataFrame に変換する。
    テーブルが存在しない場合は空の DataFrame を返す。
    """
    try:
        return spark.table("interview_prep.gold_churn_features").toPandas()
    except Exception as e:
        print(f"[ERROR] gold_churn_features の読み込みに失敗しました: {e}")
        return pd.DataFrame()


# ──────────────────────────────────────────────
# アプリ起動時にデータをキャッシュ
# （Gold テーブルは集計済みの小さなテーブルのため毎回クエリしない）
# ──────────────────────────────────────────────

df_kpi   = load_kpi_data()
df_churn = load_churn_data()

# タイトル一覧をドロップダウンの選択肢として用意
TITLE_OPTIONS = ["全タイトル"] + (
    sorted(df_kpi["title_id"].unique().tolist()) if not df_kpi.empty else []
)

# ユーザー一覧を検索候補として用意
USER_OPTIONS = sorted(df_churn["user_id"].tolist()) if not df_churn.empty else []


# ──────────────────────────────────────────────
# グラフ生成関数
# ──────────────────────────────────────────────

def create_kpi_chart(selected_title: str):
    """
    選択されたタイトルで KPI テーブルをフィルタし、
    DAU 折れ線グラフと総課金額棒グラフを返す。
    テーブルが空の場合はエラーメッセージを示す空グラフを返す。
    """
    # テーブルが読み込めていない場合のエラーグラフ
    if df_kpi.empty:
        empty_fig = px.line(title="データが読み込めませんでした。テーブルを確認してください。")
        return empty_fig, empty_fig

    # タイトルでフィルタ（「全タイトル」の場合は日付ごとに合算）
    if selected_title == "全タイトル":
        df_filtered = (
            df_kpi
            .groupby("event_date", as_index=False)
            .agg(
                dau=("dau", "sum"),
                total_revenue_jpy=("total_revenue_jpy", "sum"),
            )
        )
    else:
        df_filtered = df_kpi[df_kpi["title_id"] == selected_title].copy()

    # 日付順にソート
    df_filtered = df_filtered.sort_values("event_date")

    # DAU 日別推移（折れ線グラフ・青）
    fig_dau = px.line(
        df_filtered,
        x="event_date",
        y="dau",
        title=f"DAU 日別推移　{selected_title}",
        labels={"event_date": "日付", "dau": "DAU（人）"},
        color_discrete_sequence=["#4C9BE8"],   # 青
    )
    fig_dau.update_traces(mode="lines+markers", marker=dict(size=5))
    fig_dau.update_layout(hovermode="x unified", plot_bgcolor="white", paper_bgcolor="white")

    # 総課金額 日別推移（棒グラフ・オレンジ）
    fig_revenue = px.bar(
        df_filtered,
        x="event_date",
        y="total_revenue_jpy",
        title=f"総課金額 日別推移　{selected_title}",
        labels={"event_date": "日付", "total_revenue_jpy": "課金額（円）"},
        color_discrete_sequence=["#F4A261"],   # オレンジ
    )
    fig_revenue.update_layout(hovermode="x unified", plot_bgcolor="white", paper_bgcolor="white")

    return fig_dau, fig_revenue


# ──────────────────────────────────────────────
# チャーンリスク判定関数
# ──────────────────────────────────────────────

def calc_churn_risk(play_days: int, purchase_count: int) -> str:
    """
    直近 30 日のプレイ日数と課金回数からチャーンリスクを判定する。
    高リスク：play_days_last30 が 5 日以下 かつ purchase_count_last30 が 0
    低リスク：上記以外
    """
    if play_days <= 5 and purchase_count == 0:
        return "🔴 高リスク"
    return "🟢 低リスク"


def search_user(user_id: str):
    """
    user_id でチャーン特徴量テーブルを検索し、
    直近 30 日のメトリクスとチャーンリスク判定を返す。
    検索結果が 0 件の場合は日本語エラーメッセージを返す。
    """
    # テーブルが読み込めていない場合
    if df_churn.empty:
        return "データが読み込めていません", "－", "－", "－", "－"

    user_id = user_id.strip()

    # 入力が空の場合
    if not user_id:
        return "user_id を入力してください", "－", "－", "－", "－"

    # ユーザーを検索
    row = df_churn[df_churn["user_id"] == user_id]

    # 検索結果が 0 件の場合
    if row.empty:
        return f"ユーザー「{user_id}」は見つかりませんでした", "－", "－", "－", "－"

    r = row.iloc[0]

    play_days      = int(r["play_days_last30"])
    play_seconds   = int(r["total_play_seconds_last30"])
    purchase_count = int(r["purchase_count_last30"])
    revenue        = int(r["total_revenue_jpy_last30"])

    # プレイ時間を「XX 時間 YY 分」形式に変換
    play_hours, play_mins = divmod(play_seconds // 60, 60)
    play_time_str = f"{play_hours} 時間 {play_mins} 分（{play_seconds:,} 秒）"

    return (
        f"{play_days} 日",
        play_time_str,
        f"{purchase_count} 回",
        f"¥{revenue:,}",
        calc_churn_risk(play_days, purchase_count),
    )


# ──────────────────────────────────────────────
# Gradio UI の構築
# ──────────────────────────────────────────────

with gr.Blocks(title="モバイルゲーム KPI ダッシュボード") as app:

    gr.Markdown("# 📊 モバイルゲーム KPI ダッシュボード")

    with gr.Tabs():

        # ────────────────────────────
        # タブ①：KPI ダッシュボード（経営層向け）
        # ────────────────────────────
        with gr.Tab("📈 KPI ダッシュボード（経営層向け）"):

            gr.Markdown("### タイトルを選択するとグラフがリアルタイムで更新されます")

            title_dropdown = gr.Dropdown(
                choices=TITLE_OPTIONS,
                value="全タイトル",
                label="タイトル",
                interactive=True,
            )

            with gr.Row():
                plot_dau     = gr.Plot(label="DAU 日別推移")
                plot_revenue = gr.Plot(label="総課金額 日別推移")

            # ドロップダウン変更時にリアルタイムでグラフを更新
            title_dropdown.change(
                fn=create_kpi_chart,
                inputs=title_dropdown,
                outputs=[plot_dau, plot_revenue],
            )

            # 初期表示（全タイトル）
            app.load(
                fn=create_kpi_chart,
                inputs=title_dropdown,
                outputs=[plot_dau, plot_revenue],
            )

        # ────────────────────────────
        # タブ②：チャーンリスク確認画面（ML エンジニア向け）
        # ────────────────────────────
        with gr.Tab("🔍 チャーンリスク確認（ML エンジニア向け）"):

            gr.Markdown("### user_id を入力して直近 30 日の行動パターンを確認します")

            with gr.Row():
                user_input = gr.Dropdown(
                    choices=USER_OPTIONS,
                    label="user_id を選択または入力",
                    allow_custom_value=True,
                    interactive=True,
                    scale=4,
                )
                search_btn = gr.Button("検索", variant="primary", scale=1)

            gr.Markdown("#### 直近 30 日のメトリクス")

            # メトリクスをカード形式で表示（2列 × 2行）
            with gr.Row():
                out_play_days      = gr.Textbox(label="🎮 プレイ日数",   interactive=False, show_copy_button=False)
                out_play_time      = gr.Textbox(label="⏱ 総プレイ時間", interactive=False, show_copy_button=False)
            with gr.Row():
                out_purchase_count = gr.Textbox(label="💳 課金回数",     interactive=False, show_copy_button=False)
                out_revenue        = gr.Textbox(label="💴 課金総額",     interactive=False, show_copy_button=False)

            gr.Markdown("#### チャーンリスク判定")
            gr.Markdown(
                "> **判定基準**：直近 30 日のプレイ日数 ≤ 5 日 **かつ** 課金回数 = 0 → 🔴 高リスク  ／  それ以外 → 🟢 低リスク"
            )

            out_churn_risk = gr.Textbox(
                label="チャーンリスク",
                interactive=False,
                show_copy_button=False,
                text_align="center",
            )

            # 検索ボタン押下時にリアルタイムで結果を表示
            search_btn.click(
                fn=search_user,
                inputs=user_input,
                outputs=[out_play_days, out_play_time, out_purchase_count, out_revenue, out_churn_risk],
            )

            # user_id 入力変更時にもリアルタイムで反映
            user_input.change(
                fn=search_user,
                inputs=user_input,
                outputs=[out_play_days, out_play_time, out_purchase_count, out_revenue, out_churn_risk],
            )


# ──────────────────────────────────────────────
# アプリの起動
#
# Databricks Apps：
#   app オブジェクトをモジュールレベルに置くだけでよい（launch() 不要）
#
# Databricks ノートブックで動作確認する場合：
#   share=True で ngrok 公開 URL が発行される
#   → 出力の "Running on public URL: https://xxxx.gradio.live" を開く
# ──────────────────────────────────────────────

app.launch(
    share=True,            # ngrok 経由の公開 URL を発行（ノートブック確認用）
    server_name="0.0.0.0", # クラスター外からのリクエストを受け付ける
)
