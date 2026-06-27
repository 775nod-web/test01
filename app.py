# Databricks Apps（Gradio）用
# モバイルゲーム KPI ダッシュボード
#
# 依存ライブラリのインストール（初回起動時のみ実行される）
%pip install gradio plotly --quiet

#
# タブ①：KPI ダッシュボード（経営層向け）
#   - title_id でフィルタリング
#   - DAU 日別推移（折れ線グラフ）
#   - 総課金額日別推移（棒グラフ）
#
# タブ②：チャーン予測特徴量（ML エンジニア向け）
#   - user_id で検索
#   - 直近 30 日の特徴量表示
#   - 簡易チャーンリスクスコア表示
#
# 前提：spark オブジェクトは Databricks Apps 環境でグローバルに利用可能

import gradio as gr
import plotly.graph_objects as go
import pandas as pd
from pyspark.sql import functions as F


# ──────────────────────────────────────────────
# Gold テーブルの読み込み
# Databricks Apps 起動時に一度だけ読み込んでキャッシュする
# ──────────────────────────────────────────────

# KPI 集計テーブルを Pandas DataFrame に変換（ダッシュボード表示用）
df_kpi = (
    spark.table("interview_prep.gold_kpi_daily")
    .orderBy("event_date", "title_id")
    .toPandas()
)

# チャーン予測特徴量テーブルを Pandas DataFrame に変換（ユーザー検索用）
df_churn = (
    spark.table("interview_prep.gold_churn_features")
    .orderBy("user_id")
    .toPandas()
)

# タイトル一覧を取得（フィルタのドロップダウンに使用）
title_options = ["全タイトル"] + sorted(df_kpi["title_id"].unique().tolist())

# user_id 一覧を取得（検索のオートコンプリートに使用）
user_options = sorted(df_churn["user_id"].tolist())


# ──────────────────────────────────────────────
# タブ① KPI ダッシュボード ロジック
# ──────────────────────────────────────────────

def render_kpi_charts(selected_title: str):
    """
    選択されたタイトルで df_kpi をフィルタし、
    DAU 折れ線グラフと総課金額棒グラフを返す
    """
    # タイトルでフィルタリング（「全タイトル」の場合は日付ごとに合算）
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

    # DAU 日別推移（折れ線グラフ）
    fig_dau = go.Figure()
    fig_dau.add_trace(
        go.Scatter(
            x=df_filtered["event_date"],
            y=df_filtered["dau"],
            mode="lines+markers",
            name="DAU",
            line=dict(color="#4C9BE8", width=2),
            marker=dict(size=5),
        )
    )
    fig_dau.update_layout(
        title=f"DAU 日別推移　{selected_title}",
        xaxis_title="日付",
        yaxis_title="DAU（人）",
        hovermode="x unified",
        plot_bgcolor="white",
        paper_bgcolor="white",
    )

    # 総課金額 日別推移（棒グラフ）
    fig_revenue = go.Figure()
    fig_revenue.add_trace(
        go.Bar(
            x=df_filtered["event_date"],
            y=df_filtered["total_revenue_jpy"],
            name="総課金額",
            marker_color="#F4A261",
        )
    )
    fig_revenue.update_layout(
        title=f"総課金額 日別推移　{selected_title}",
        xaxis_title="日付",
        yaxis_title="課金額（円）",
        hovermode="x unified",
        plot_bgcolor="white",
        paper_bgcolor="white",
    )

    return fig_dau, fig_revenue


# ──────────────────────────────────────────────
# タブ② チャーン予測特徴量 ロジック
# ──────────────────────────────────────────────

def calc_churn_risk(play_days: int, purchase_count: int) -> str:
    """
    簡易チャーンリスク判定：
      直近 30 日のプレイ日数が 5 日以下 かつ 課金回数が 0 → 高リスク
      それ以外 → 低リスク
    """
    if play_days <= 5 and purchase_count == 0:
        return "🔴 高リスク"
    return "🟢 低リスク"


def search_user(user_id: str):
    """
    user_id で df_churn を検索し、特徴量とチャーンリスクを返す
    """
    # 入力値のトリム（スペース混入対策）
    user_id = user_id.strip()

    # 該当ユーザーを検索
    row = df_churn[df_churn["user_id"] == user_id]

    if row.empty:
        # 見つからない場合はエラーメッセージを返す
        return (
            "ユーザーが見つかりません",   # play_days
            "－",                          # total_play_seconds
            "－",                          # purchase_count
            "－",                          # total_revenue_jpy
            "－",                          # churn_risk
        )

    r = row.iloc[0]   # 最初の1行を取得

    play_days      = int(r["play_days_last30"])
    play_seconds   = int(r["total_play_seconds_last30"])
    purchase_count = int(r["purchase_count_last30"])
    revenue        = int(r["total_revenue_jpy_last30"])
    churn_risk     = calc_churn_risk(play_days, purchase_count)

    # プレイ時間を「XX 時間 YY 分」形式に変換して可読性を上げる
    play_hours, play_mins = divmod(play_seconds // 60, 60)
    play_time_str = f"{play_hours} 時間 {play_mins} 分  （{play_seconds:,} 秒）"

    return (
        f"{play_days} 日",
        play_time_str,
        f"{purchase_count} 回",
        f"¥{revenue:,}",
        churn_risk,
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

            gr.Markdown("### タイトルを選択してグラフを表示します")

            # タイトルフィルタ（ドロップダウン）
            title_dropdown = gr.Dropdown(
                choices=title_options,
                value="全タイトル",
                label="タイトル",
                interactive=True,
            )

            # グラフ表示エリア（2列レイアウト）
            with gr.Row():
                plot_dau     = gr.Plot(label="DAU 日別推移")
                plot_revenue = gr.Plot(label="総課金額 日別推移")

            # タイトル選択時にグラフを更新
            title_dropdown.change(
                fn=render_kpi_charts,
                inputs=title_dropdown,
                outputs=[plot_dau, plot_revenue],
            )

            # 初期表示（全タイトル）
            app.load(
                fn=render_kpi_charts,
                inputs=title_dropdown,
                outputs=[plot_dau, plot_revenue],
            )

        # ────────────────────────────
        # タブ②：チャーン予測特徴量（ML エンジニア向け）
        # ────────────────────────────
        with gr.Tab("🔍 チャーン予測特徴量（ML エンジニア向け）"):

            gr.Markdown("### user_id を入力してユーザーの特徴量を確認します")

            # user_id 検索ボックス（オートコンプリートあり）
            user_input = gr.Dropdown(
                choices=user_options,
                label="user_id を選択または入力",
                allow_custom_value=True,
                interactive=True,
            )

            search_btn = gr.Button("検索", variant="primary")

            gr.Markdown("#### 直近 30 日の特徴量")

            # 特徴量の表示（各指標を縦並びのラベルで表示）
            with gr.Row():
                out_play_days      = gr.Textbox(label="プレイ日数",  interactive=False)
                out_play_time      = gr.Textbox(label="総プレイ時間", interactive=False)
            with gr.Row():
                out_purchase_count = gr.Textbox(label="課金回数",    interactive=False)
                out_revenue        = gr.Textbox(label="課金総額",     interactive=False)

            gr.Markdown("#### チャーンリスク判定")
            gr.Markdown(
                "ルール：直近 30 日のプレイ日数 ≤ 5 日 かつ 課金回数 = 0 → **高リスク**"
            )

            out_churn_risk = gr.Textbox(
                label="チャーンリスク",
                interactive=False,
                text_align="center",
            )

            # 検索ボタン押下時にユーザー情報を表示
            search_btn.click(
                fn=search_user,
                inputs=user_input,
                outputs=[
                    out_play_days,
                    out_play_time,
                    out_purchase_count,
                    out_revenue,
                    out_churn_risk,
                ],
            )


# ──────────────────────────────────────────────
# アプリの起動
# Databricks Apps では app オブジェクトを返すだけでよい
# ローカルデバッグ時は launch() を呼び出す
# ──────────────────────────────────────────────

if __name__ == "__main__":
    # ローカル確認用（Databricks Apps 上では不要）
    app.launch()
