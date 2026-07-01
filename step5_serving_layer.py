# Databricks notebook source
# MAGIC %md
# MAGIC # Step 5: Serving Layer
# MAGIC
# MAGIC ## 1. サービス選定
# MAGIC
# MAGIC ### ビジネス目的と必要機能の対応
# MAGIC
# MAGIC | ビジネス目的 | 必要な機能 |
# MAGIC |---|---|
# MAGIC | 経営層向け全社KPIダッシュボード（短期PoC） | ノーコードのビジュアライゼーション・共有URL |
# MAGIC | 売上成長鈍化の理由特定 | 複数テーブルを横断するアドホッククエリ |
# MAGIC | Free→有料転換率・解約モニタリング | 定期更新される指標・トレンド表示 |
# MAGIC | CSチーム向け解約リスクリスト | フィルタリング可能なテーブル表示 |
# MAGIC | 解約リスクユーザーの早期発見・通知 | 自動アラート（Email / Slack） |
# MAGIC | Databricks上での継続的な分析基盤（長期） | SQL標準・Delta統合・拡張性 |
# MAGIC
# MAGIC ### Databricks Free Edition サービス比較
# MAGIC
# MAGIC | サービス | 今回の適合性 | 理由 |
# MAGIC |---|---|---|
# MAGIC | **Databricks SQL（SQL Warehouse + Dashboard + Alerts）** | ✅ **採用** | 全ビジネス目的をカバー。Dashboard・Alerts・SQL Editorが一体提供 |
# MAGIC | Databricks Apps（Streamlit等） | ✅ 利用可能だが今回は不採用 | PoC段階ではノーコードのDashboardで十分。カスタムUI不要 |
# MAGIC | Delta Live Tables | ❌ 今回は不採用 | ストリーミングパイプライン向け。バッチで要件を満たせる |
# MAGIC | MLflow | ❌ 今回は不採用 | ML実験管理用。今回のユースケースにMLは不要 |
# MAGIC | Delta Sharing | ❌ 今回は不採用 | 外部組織へのデータ共有用。内部利用のみ |
# MAGIC
# MAGIC ### 採用: Databricks SQL（SQL Warehouse）
# MAGIC
# MAGIC 1. **SQL Dashboard** → 経営層KPIダッシュボードをノーコードで構築・共有URL発行
# MAGIC 2. **SQL Alerts** → `churn_risk_flag=true` 検知時にCSチームへSlack/Email自動通知
# MAGIC 3. **SQL Editor** → 売上鈍化の原因特定などアドホッククエリをインタラクティブに実行
# MAGIC 4. **SQL Warehouse** → Serverlessコンピュートで低コスト・オートスケール
# MAGIC 5. **SQL Views（Semantic Layer）** → Gold LayerをビューでラップしてSQLユーザーへ一貫したインターフェースを提供
# MAGIC
# MAGIC ### 実装構成
# MAGIC ```
# MAGIC Gold Layer（Delta Tables）
# MAGIC       │
# MAGIC       ▼
# MAGIC serving database（SQL Views）← Semantic Layer / アクセス制御境界
# MAGIC       │
# MAGIC       ├── Databricks SQL Dashboard  ← 経営層KPIダッシュボード（4ページ構成）
# MAGIC       ├── Databricks SQL Editor     ← アドホック分析（CSチーム・アナリスト）
# MAGIC       └── Databricks SQL Alerts     ← 解約リスク自動通知（3件）
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. 事前準備：Gold Layer パフォーマンス最適化
# MAGIC
# MAGIC SQL Warehouse からのクエリ応答速度を最大化するため、
# MAGIC Gold テーブルに `OPTIMIZE + ZORDER` を適用する。
# MAGIC `ZORDER` はフィルタリング頻度の高いカラムを指定することで、
# MAGIC Delta のデータスキッピングが効くようになる。

# COMMAND ----------

print("Gold Layer OPTIMIZE + ZORDER 実行中...")

optimize_configs = [
    ("gold.daily_kpi",            "kpi_date",               "経営層KPIダッシュボード: 日付フィルタ高速化"),
    ("gold.sales_per_plan",       "sales_month, plan_type", "プラン別売上トレンド: 月×プランフィルタ高速化"),
    ("gold.failed_payment_user",  "user_id",                "CSチーム解約リスクリスト: ユーザーID検索高速化"),
    ("gold.data_quality_summary", "run_date, source_table", "DQモニタリング: 実行日×テーブルフィルタ高速化"),
]

for table, zorder_cols, comment in optimize_configs:
    spark.sql(f"OPTIMIZE {table} ZORDER BY ({zorder_cols})")
    print(f"  ✅ {table} — {comment}")

print("\nGold Layer 最適化完了")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Serving データベース初期化

# COMMAND ----------

spark.sql("CREATE DATABASE IF NOT EXISTS serving COMMENT 'Databricks SQL向けServing Layer — SQL Viewsによるセマンティックレイヤー'")
spark.sql("USE serving")
print("✅ serving データベース準備完了")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. SQL Views 作成（Semantic Layer）
# MAGIC
# MAGIC ### ビュー設計方針
# MAGIC - Gold テーブルを直接公開せず**ビュー経由でアクセス制御境界**を設ける
# MAGIC - Databricks SQL Dashboard の各ウィジェットが 1 ビューに対応
# MAGIC - 計算済み指標・優先度ラベルを付与し、SQLユーザーがそのまま使えるようにする

# COMMAND ----------

# MAGIC %md
# MAGIC ### View 1: 経営層向け全社KPIサマリー
# MAGIC
# MAGIC **対応ビジネス目的**:
# MAGIC - 経営層向け全社KPIダッシュボード
# MAGIC - 売上成長鈍化の理由特定（前日比増減を可視化）
# MAGIC - Free→有料転換率の把握

# COMMAND ----------

spark.sql("""
CREATE OR REPLACE VIEW serving.v_executive_daily_kpi
COMMENT '経営層向け全社KPIサマリー — Databricks SQL Dashboard用'
AS
SELECT
    kpi_date,
    dau,
    new_signup_count,
    total_paid_users,
    total_free_users,
    (total_paid_users + total_free_users)                                                      AS total_users,
    daily_revenue,
    upgrade_click_count,
    cancel_click_count,
    new_paid_conversion_count,
    churn_count,
    free_to_paid_rate,
    -- 有料転換率（全ユーザーに占める有料ユーザー比率）
    ROUND(total_paid_users * 100.0 / NULLIF(total_paid_users + total_free_users, 0), 2)        AS paid_ratio_pct,
    -- 有料ユーザー1人あたり収益（収益効率の指標）
    ROUND(daily_revenue / NULLIF(total_paid_users, 0), 2)                                      AS revenue_per_paid_user,
    -- 前日比 Net 有料ユーザー増減（成長鈍化の早期検知）
    total_paid_users - LAG(total_paid_users) OVER (ORDER BY kpi_date)                          AS net_paid_user_change,
    -- 前日比収益増減
    daily_revenue - LAG(daily_revenue) OVER (ORDER BY kpi_date)                                AS net_revenue_change
FROM gold.daily_kpi
ORDER BY kpi_date DESC
""")
print("✅ v_executive_daily_kpi 作成完了")

# COMMAND ----------

# MAGIC %md
# MAGIC ### View 2: プラン別売上トレンド（MoM成長率）
# MAGIC
# MAGIC **対応ビジネス目的**:
# MAGIC - 売上成長鈍化の理由特定（どのプランで鈍化しているか）
# MAGIC - 特定プランでの問題特定

# COMMAND ----------

spark.sql("""
CREATE OR REPLACE VIEW serving.v_revenue_trend
COMMENT 'プラン別月次売上トレンド — MoM成長率で売上鈍化の原因プランを特定'
AS
SELECT
    sales_month,
    plan_type,
    total_revenue,
    transaction_count,
    success_count,
    failed_count,
    avg_transaction_amount,
    new_subscriber_count,
    churned_subscriber_count,
    active_subscriber_count,
    failed_payment_rate,
    -- 加入者あたり収益（プラン価値の指標）
    ROUND(total_revenue / NULLIF(active_subscriber_count, 0), 2)                  AS revenue_per_active_sub,
    -- MoM売上成長率（成長鈍化の原因プランを特定）
    LAG(total_revenue) OVER (PARTITION BY plan_type ORDER BY sales_month)          AS prev_month_revenue,
    ROUND(
        (total_revenue
         - LAG(total_revenue) OVER (PARTITION BY plan_type ORDER BY sales_month)
        ) * 100.0
        / NULLIF(
            LAG(total_revenue) OVER (PARTITION BY plan_type ORDER BY sales_month)
          , 0),
        2
    )                                                                              AS mom_revenue_growth_pct,
    -- MoM加入者増減
    active_subscriber_count
    - LAG(active_subscriber_count) OVER (PARTITION BY plan_type ORDER BY sales_month) AS mom_subscriber_change
FROM gold.sales_per_plan
ORDER BY sales_month DESC, plan_type
""")
print("✅ v_revenue_trend 作成完了")

# COMMAND ----------

# MAGIC %md
# MAGIC ### View 3: Free→有料 転換ファネル
# MAGIC
# MAGIC **対応ビジネス目的**:
# MAGIC - Free ユーザーの有料転換率の把握
# MAGIC - 既存有料ユーザーの離脱モニタリング

# COMMAND ----------

spark.sql("""
CREATE OR REPLACE VIEW serving.v_conversion_funnel
COMMENT 'Free→有料転換ファネル — 転換率・解約クリック率・チャーン率の日次推移'
AS
SELECT
    kpi_date,
    DATE_TRUNC('MM', kpi_date)                                                              AS funnel_month,
    dau,
    total_paid_users,
    total_free_users,
    (total_paid_users + total_free_users)                                                   AS total_users,
    new_signup_count,
    new_paid_conversion_count,
    upgrade_click_count,
    cancel_click_count,
    churn_count,
    free_to_paid_rate,
    -- 有料ユーザー比率
    ROUND(total_paid_users * 100.0 / NULLIF(total_paid_users + total_free_users, 0), 2)    AS paid_ratio_pct,
    -- 解約クリック率（有料ユーザーに占める解約クリック比率）
    ROUND(cancel_click_count * 100.0 / NULLIF(total_paid_users, 0), 2)                     AS cancel_click_rate_pct,
    -- チャーン率（有料ユーザーに占めるチャーン数比率）
    ROUND(churn_count * 100.0 / NULLIF(total_paid_users, 0), 2)                            AS churn_rate_pct
FROM gold.daily_kpi
ORDER BY kpi_date DESC
""")
print("✅ v_conversion_funnel 作成完了")

# COMMAND ----------

# MAGIC %md
# MAGIC ### View 4: プラン別健全性スコアボード
# MAGIC
# MAGIC **対応ビジネス目的**:
# MAGIC - 特定プラン・国・セグメントでの問題特定
# MAGIC - 既存有料ユーザーの離脱モニタリング

# COMMAND ----------

spark.sql("""
CREATE OR REPLACE VIEW serving.v_plan_health
COMMENT 'プラン別健全性スコアボード — 解約リスク・決済失敗率をプラン単位で集計'
AS
SELECT
    plan_type,
    COUNT(DISTINCT user_id)                                                                       AS total_paid_users,
    SUM(CASE WHEN churn_risk_flag = TRUE THEN 1 ELSE 0 END)                                       AS churn_risk_count,
    ROUND(
        SUM(CASE WHEN churn_risk_flag = TRUE THEN 1 ELSE 0 END) * 100.0
        / NULLIF(COUNT(DISTINCT user_id), 0), 2)                                                  AS churn_risk_rate_pct,
    SUM(CASE WHEN has_recent_cancel_click = TRUE THEN 1 ELSE 0 END)                               AS cancel_click_users,
    ROUND(
        SUM(CASE WHEN has_recent_cancel_click = TRUE THEN 1 ELSE 0 END) * 100.0
        / NULLIF(COUNT(DISTINCT user_id), 0), 2)                                                  AS cancel_click_rate_pct,
    ROUND(AVG(total_failed_count), 2)                                                             AS avg_failed_payment_count,
    SUM(total_failed_count)                                                                       AS total_failed_count,
    -- 健全性判定（Databricks SQL Dashboard のカラー表示に対応）
    CASE
        WHEN SUM(CASE WHEN churn_risk_flag = TRUE THEN 1 ELSE 0 END) * 100.0
             / NULLIF(COUNT(DISTINCT user_id), 0) >= 20 THEN '🔴 Critical'
        WHEN SUM(CASE WHEN churn_risk_flag = TRUE THEN 1 ELSE 0 END) * 100.0
             / NULLIF(COUNT(DISTINCT user_id), 0) >= 10 THEN '🟡 Warning'
        ELSE '🟢 Healthy'
    END                                                                                           AS health_status
FROM gold.failed_payment_user
GROUP BY plan_type
ORDER BY churn_risk_rate_pct DESC
""")
print("✅ v_plan_health 作成完了")

# COMMAND ----------

# MAGIC %md
# MAGIC ### View 5: CSチーム向け解約リスクアクションリスト
# MAGIC
# MAGIC **対応ビジネス目的**:
# MAGIC - 解約リスクユーザーをCSチームが早期発見してアクションできるリスト提供
# MAGIC - 特定プラン・国・セグメントでの問題特定
# MAGIC
# MAGIC **SQL Alerts との連携**:
# MAGIC このビューを Databricks SQL Alerts のクエリソースとして設定し、
# MAGIC `churn_risk_flag=true` のレコード数 > 0 で CSチームへ Slack/Email 自動通知する。

# COMMAND ----------

spark.sql("""
CREATE OR REPLACE VIEW serving.v_churn_risk_action_list
COMMENT 'CSチーム向け解約リスクアクションリスト — SQL Alerts の通知トリガーとしても使用'
AS
SELECT
    user_id,
    plan_type,
    country_code,
    user_segment,
    is_active,
    total_failed_count,
    total_success_count,
    latest_payment_date,
    latest_payment_status,
    latest_amount,
    has_recent_cancel_click,
    churn_risk_flag,
    -- アクション優先度（CSチームがトリアージに使用）
    CASE
        WHEN churn_risk_flag = TRUE  AND has_recent_cancel_click = TRUE
            THEN '🔴 P0 — 即時コンタクト (決済失敗+解約クリック確認済)'
        WHEN churn_risk_flag = TRUE  AND has_recent_cancel_click = FALSE
            THEN '🟡 P1 — 今週中にフォロー (決済失敗のみ)'
        WHEN churn_risk_flag = FALSE AND has_recent_cancel_click = TRUE
            THEN '🟠 P2 — 今月中にフォロー (解約クリックのみ)'
        ELSE '🟢 P3 — 定期モニタリング'
    END                                                         AS action_priority,
    -- 決済失敗パターン（CSのアプローチ判断に使用）
    CASE
        WHEN total_failed_count >= 3 THEN '繰り返し失敗 (カード情報更新を促す)'
        WHEN total_failed_count = 2  THEN '複数回失敗 (支払い方法変更を提案)'
        WHEN total_failed_count = 1  THEN '初回失敗 (一時的エラーの可能性)'
        ELSE '決済失敗なし'
    END                                                         AS failure_pattern,
    -- 最終決済からの経過日数（緊急度の目安）
    DATEDIFF(CURRENT_DATE(), latest_payment_date)               AS days_since_last_payment
FROM gold.failed_payment_user
ORDER BY
    churn_risk_flag DESC,
    has_recent_cancel_click DESC,
    total_failed_count DESC
""")
print("✅ v_churn_risk_action_list 作成完了")

# COMMAND ----------

# MAGIC %md
# MAGIC ### View 6: データ品質モニタリング
# MAGIC
# MAGIC **対応ビジネス目的**:
# MAGIC - Databricks上での継続的な分析基盤（長期）
# MAGIC - Silver Layer への昇格可否判定と品質劣化の早期検知

# COMMAND ----------

spark.sql("""
CREATE OR REPLACE VIEW serving.v_data_quality_monitor
COMMENT 'データ品質モニタリング — Silver Layer昇格可否と品質劣化の早期検知'
AS
SELECT
    run_date,
    source_table,
    dq_check_name,
    total_records,
    issue_count,
    description,
    ROUND(issue_rate * 100.0, 2)                               AS issue_rate_pct,
    -- 品質ステータス（Databricks SQL のカラー条件付き書式に対応）
    CASE
        WHEN issue_rate * 100.0 >= 10 THEN '🔴 Major   — 即時調査が必要'
        WHEN issue_rate * 100.0 >= 3  THEN '⚠️  Warning — 要監視'
        ELSE '✅ Normal  — 正常範囲内'
    END                                                        AS quality_status,
    -- Silver Layer 昇格可否（issue_rate >= 10% は昇格ブロック推奨）
    CASE
        WHEN issue_rate * 100.0 >= 10 THEN '🚫 昇格ブロック推奨'
        ELSE '✅ 昇格可'
    END                                                        AS silver_promotion_gate
FROM gold.data_quality_summary
ORDER BY run_date DESC, issue_rate DESC
""")
print("✅ v_data_quality_monitor 作成完了")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Databricks SQL Alerts 設定ガイド
# MAGIC
# MAGIC **設定場所**: Databricks SQL > Alerts > Create Alert
# MAGIC
# MAGIC SQL Alerts は以下のクエリを定期実行し、条件を満たした場合に通知する。
# MAGIC ビューがセマンティックレイヤーとして機能しているため、
# MAGIC アラートクエリはシンプルに保てる。

# COMMAND ----------

alert_definitions = [
    {
        "name": "[CS] 解約リスクP0ユーザー検知",
        "purpose": "churn_risk_flag=true かつ解約クリックありのユーザーをCSチームへSlack/Email通知",
        "trigger_condition": "結果の値 > 0",
        "notification_target": "CSチーム Slack #cs-alerts",
        "frequency": "1時間ごと",
        "query": """SELECT COUNT(*) AS p0_churn_risk_count
FROM serving.v_churn_risk_action_list
WHERE action_priority LIKE '%P0%'""",
    },
    {
        "name": "[Biz] 有料転換率2pt低下検知",
        "purpose": "paid_ratio_pct が前日比2ポイント以上低下した場合に経営層へ通知",
        "trigger_condition": "結果の値 > 0",
        "notification_target": "経営層 Email",
        "frequency": "日次",
        "query": """SELECT COUNT(*) AS conversion_drop_flag
FROM (
    SELECT
        kpi_date,
        paid_ratio_pct,
        LAG(paid_ratio_pct) OVER (ORDER BY kpi_date) AS prev_paid_ratio_pct
    FROM serving.v_executive_daily_kpi
) t
WHERE kpi_date = CURRENT_DATE() - INTERVAL 1 DAY
  AND (prev_paid_ratio_pct - paid_ratio_pct) >= 2.0""",
    },
    {
        "name": "[Data] データ品質劣化検知",
        "purpose": "issue_rate >= 10% のDQチェックを検知してデータエンジニアに通知",
        "trigger_condition": "結果の値 > 0",
        "notification_target": "データエンジニア Email",
        "frequency": "日次（Gold Layer更新後）",
        "query": """SELECT COUNT(*) AS critical_dq_count
FROM serving.v_data_quality_monitor
WHERE issue_rate_pct >= 10.0
  AND run_date = CURRENT_DATE()""",
    },
]

print("=" * 60)
print("Databricks SQL Alerts 設定ガイド")
print("設定場所: Databricks SQL > Alerts > Create Alert")
print("=" * 60)
for i, a in enumerate(alert_definitions, 1):
    print(f"\n--- Alert {i}: {a['name']} ---")
    print(f"  目的      : {a['purpose']}")
    print(f"  通知先    : {a['notification_target']}")
    print(f"  実行頻度  : {a['frequency']}")
    print(f"  トリガー  : {a['trigger_condition']}")
    print(f"  クエリ:\n{a['query']}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Databricks SQL Dashboard 構成ガイド
# MAGIC
# MAGIC **設定場所**: Databricks SQL > Dashboards > Create Dashboard
# MAGIC
# MAGIC 各ビューが Dashboard の 1ウィジェットに対応する。
# MAGIC
# MAGIC | ページ | ウィジェット | ビュー | 可視化タイプ |
# MAGIC |---|---|---|---|
# MAGIC | 全社KPI（経営層） | 有料ユーザー数推移 | v_executive_daily_kpi | Line Chart（kpi_date × total_paid_users）|
# MAGIC | 〃 | 日次収益推移 | v_executive_daily_kpi | Bar Chart（kpi_date × daily_revenue）|
# MAGIC | 〃 | Net有料ユーザー増減 | v_executive_daily_kpi | Bar Chart（正=緑/負=赤）|
# MAGIC | 売上分析（PM） | プラン別月次収益 | v_revenue_trend | Stacked Bar（sales_month × plan_type）|
# MAGIC | 〃 | MoM成長率 | v_revenue_trend | Line Chart（mom_revenue_growth_pct）|
# MAGIC | 〃 | プラン健全性 | v_plan_health | Table（health_status カラー列）|
# MAGIC | CSアクション | 解約リスクリスト | v_churn_risk_action_list | Table（action_priority でソート）|
# MAGIC | 〃 | 転換ファネル | v_conversion_funnel | Line Chart（paid_ratio_pct / churn_rate_pct）|
# MAGIC | データ品質 | DQステータス | v_data_quality_monitor | Table（quality_status カラー列）|

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. 動作確認

# COMMAND ----------

print("=" * 60)
print("serving データベース — ビュー一覧")
print("=" * 60)
spark.sql("SHOW VIEWS IN serving").show(truncate=False)

# COMMAND ----------

print("--- v_executive_daily_kpi (先頭5件) ---")
spark.sql("SELECT kpi_date, total_paid_users, total_free_users, paid_ratio_pct, daily_revenue, net_paid_user_change FROM serving.v_executive_daily_kpi LIMIT 5").show(truncate=False)

print("--- v_revenue_trend (先頭5件) ---")
spark.sql("SELECT sales_month, plan_type, total_revenue, active_subscriber_count, revenue_per_active_sub, mom_revenue_growth_pct FROM serving.v_revenue_trend LIMIT 5").show(truncate=False)

print("--- v_conversion_funnel (先頭5件) ---")
spark.sql("SELECT kpi_date, total_paid_users, paid_ratio_pct, cancel_click_rate_pct, churn_rate_pct FROM serving.v_conversion_funnel LIMIT 5").show(truncate=False)

print("--- v_plan_health ---")
spark.sql("SELECT * FROM serving.v_plan_health").show(truncate=False)

print("--- v_churn_risk_action_list (churn_risk=true のみ) ---")
spark.sql("SELECT user_id, plan_type, country_code, user_segment, action_priority, failure_pattern, days_since_last_payment FROM serving.v_churn_risk_action_list WHERE churn_risk_flag = TRUE").show(truncate=False)

print("--- v_data_quality_monitor ---")
spark.sql("SELECT source_table, dq_check_name, issue_rate_pct, quality_status, silver_promotion_gate FROM serving.v_data_quality_monitor").show(truncate=False)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. 完了サマリー

# COMMAND ----------

print("""
╔══════════════════════════════════════════════════════════════╗
║           Step 5: Serving Layer 構築完了                    ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  採用サービス: Databricks SQL (SQL Warehouse)               ║
║                                                              ║
║  作成ビュー (serving データベース)                           ║
║    v_executive_daily_kpi     — 経営層KPIサマリー            ║
║    v_revenue_trend           — プラン別売上MoM分析          ║
║    v_conversion_funnel       — Free→有料転換ファネル        ║
║    v_plan_health             — プラン健全性スコアボード      ║
║    v_churn_risk_action_list  — CSアクションリスト           ║
║    v_data_quality_monitor    — DQモニタリング               ║
║                                                              ║
║  Gold Layer OPTIMIZE + ZORDER 適用済み                      ║
║                                                              ║
║  次のアクション (Databricks SQL UI)                          ║
║    1. SQL Warehouse を起動                                   ║
║    2. Dashboard を4ページ構成で作成                          ║
║    3. Alerts を3件設定 (CS / Biz / Data)                   ║
║    4. 経営層・CSチームに Dashboard URL を共有               ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝

Medallion Architecture 全ステップ完了:
  sample_src → bronze → silver → gold → serving
                                          └─▶ Databricks SQL Dashboard / Alerts
""")
