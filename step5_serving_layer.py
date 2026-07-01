# Databricks notebook source
# MAGIC %md
# MAGIC # Step 5: Serving Layer — Databricks Free Edition サービス選定と実装
# MAGIC
# MAGIC ## サービス選定の根拠
# MAGIC
# MAGIC ### ビジネス目的の整理
# MAGIC | ビジネス目的 | 必要な機能 |
# MAGIC |---|---|
# MAGIC | 経営層向け全社KPIダッシュボード（短期PoC） | インタラクティブなビジュアライゼーション・リアルタイム更新 |
# MAGIC | 売上成長鈍化の理由特定 | 複数テーブルを横断するアドホッククエリ |
# MAGIC | Free→有料転換率・解約モニタリング | 定期的な指標更新・トレンド分析 |
# MAGIC | CSチーム向け解約リスクリスト | フィルタリング可能なリスト＋アクション優先度 |
# MAGIC | 解約リスクユーザーの早期発見 | **自動アラート通知** |
# MAGIC | Databricks上での継続的な分析基盤（長期） | SQL標準・拡張性・Deltaとの統合 |
# MAGIC
# MAGIC ### Databricks Free Edition で利用可能なサービス比較
# MAGIC | サービス | 用途 | 今回の適合性 |
# MAGIC |---|---|---|
# MAGIC | **Databricks SQL (SQL Warehouse + Dashboard + Alerts)** | BIダッシュボード・アラート | ✅ **最適** |
# MAGIC | Delta Live Tables | ストリーミングパイプライン | ❌ 今回はバッチで十分 |
# MAGIC | MLflow | ML実験管理 | ❌ 今回はML不要 |
# MAGIC | Delta Sharing | 外部組織へのデータ共有 | ❌ 内部利用のみ |
# MAGIC | Notebooks (PySpark) | ETL・探索的分析 | ⚠️ 対話的BIには不向き |
# MAGIC
# MAGIC ### ✅ 選定: **Databricks SQL (SQL Warehouse)**
# MAGIC **理由:**
# MAGIC 1. **SQL Dashboard** → 経営層向けKPIダッシュボードをノーコードで構築、共有URL発行可能
# MAGIC 2. **SQL Alerts** → `churn_risk_flag=true` ユーザー検知時にCSチームへ自動通知（Email/Slack連携）
# MAGIC 3. **SQL Editor** → アドホッククエリで売上鈍化の原因を即時調査可能
# MAGIC 4. **SQL Warehouse** → Serverlessコンピュートで低コスト・自動スケール、Free Editionで利用可能
# MAGIC 5. **SQL Views (Semantic Layer)** → Gold LayerをビューでラップしてSQLユーザーに一貫したインターフェースを提供
# MAGIC
# MAGIC ### 実装構成
# MAGIC ```
# MAGIC Gold Layer (Delta Tables)
# MAGIC       │
# MAGIC       ▼
# MAGIC serving database (SQL Views) ← Semantic Layer / アクセス制御境界
# MAGIC       │
# MAGIC       ├── Databricks SQL Dashboard  ← 経営層KPIダッシュボード
# MAGIC       ├── Databricks SQL Editor     ← アドホック分析（CSチーム・アナリスト）
# MAGIC       └── Databricks SQL Alerts     ← 解約リスク自動通知（CSチーム）
# MAGIC ```

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql.window import Window
from datetime import datetime

print("=" * 60)
print("Step 5: Serving Layer 構築開始")
print("選定サービス: Databricks SQL (SQL Warehouse + Dashboard + Alerts)")
print("=" * 60)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Serving データベース初期化

# COMMAND ----------

spark.sql("CREATE DATABASE IF NOT EXISTS serving COMMENT 'Databricks SQL向けServing Layer — SQL Viewsによるセマンティックレイヤー'")
spark.sql("USE serving")
print("✅ serving データベース準備完了")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Gold Layer パフォーマンス最適化
# MAGIC
# MAGIC SQL Warehouse からのクエリ応答速度を最大化するため、
# MAGIC Gold テーブルに OPTIMIZE + ZORDER を適用する。
# MAGIC ZORDER はフィルタリング頻度の高いカラムを指定。

# COMMAND ----------

print("Gold Layer OPTIMIZE + ZORDER 実行中...")

optimize_configs = [
    # (テーブル名, ZORDERカラム, 用途コメント)
    ("gold.daily_kpi",             "kpi_date",               "経営層KPIダッシュボード: 日付フィルタ高速化"),
    ("gold.sales_per_plan",        "sales_month, plan_type", "プラン別売上トレンド: 月×プランフィルタ高速化"),
    ("gold.failed_payment_user",   "user_id",                "CSチーム解約リスクリスト: ユーザーID検索高速化"),
    ("gold.data_quality_summary",  "run_date, source_table", "DQモニタリング: 実行日×テーブルフィルタ高速化"),
]

for table, zorder_cols, comment in optimize_configs:
    spark.sql(f"OPTIMIZE {table} ZORDER BY ({zorder_cols})")
    print(f"  ✅ {table} — {comment}")

print("\nGold Layer 最適化完了")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Serving Views 作成
# MAGIC
# MAGIC ### ビュー設計方針
# MAGIC - Gold テーブルを直接公開せず、**ビュー経由でアクセス制御境界**を設ける
# MAGIC - Databricks SQL Dashboard の各ウィジェットは 1 ビューに対応
# MAGIC - 計算済み指標・日本語コメント付きで SQL Warehouse からそのまま使用可能

# COMMAND ----------

# MAGIC %md
# MAGIC ### View 1: 経営層向け全社KPIサマリー
# MAGIC **用途**: Databricks SQL Dashboard — 「全社KPI」ページ
# MAGIC **利用者**: 経営層
# MAGIC **更新頻度**: 日次（Gold Layer再実行時に自動更新）

# COMMAND ----------

spark.sql("""
CREATE OR REPLACE VIEW serving.v_executive_daily_kpi
COMMENT '経営層向け全社KPIサマリー — Databricks SQL Dashboard用'
AS
SELECT
    kpi_date,
    total_users,
    paid_users,
    free_users,
    -- 有料転換率 (Free→Paid の状況把握)
    ROUND(paid_users * 100.0 / NULLIF(total_users, 0), 2)      AS paid_ratio_pct,
    -- 収益指標
    daily_revenue,
    ROUND(daily_revenue / NULLIF(paid_users, 0), 2)             AS revenue_per_paid_user,
    -- 解約シグナル
    cancel_click_count,
    failed_payment_count,
    -- 前日比 Net 有料ユーザー増減 (成長鈍化の早期検知)
    paid_users - LAG(paid_users) OVER (ORDER BY kpi_date)       AS net_paid_user_change,
    -- 前日比収益増減
    daily_revenue - LAG(daily_revenue) OVER (ORDER BY kpi_date) AS net_revenue_change
FROM gold.daily_kpi
ORDER BY kpi_date DESC
""")
print("✅ v_executive_daily_kpi 作成完了")

# COMMAND ----------

# MAGIC %md
# MAGIC ### View 2: プラン別売上トレンド (MoM成長率)
# MAGIC **用途**: Databricks SQL Dashboard — 「売上分析」ページ
# MAGIC **利用者**: 経営層・プロダクトマネージャー
# MAGIC **目的**: 売上成長鈍化の原因をプラン単位で特定

# COMMAND ----------

spark.sql("""
CREATE OR REPLACE VIEW serving.v_revenue_trend
COMMENT 'プラン別月次売上トレンド — MoM成長率で売上鈍化の原因プランを特定'
AS
SELECT
    sales_month,
    month_end_date,
    plan_type,
    total_revenue,
    active_subscribers,
    -- 加入者あたり収益 (プラン価値の指標)
    ROUND(total_revenue / NULLIF(active_subscribers, 0), 2)   AS revenue_per_active_sub,
    -- MoM売上成長率 (成長鈍化の原因プランを特定)
    LAG(total_revenue) OVER (
        PARTITION BY plan_type ORDER BY sales_month
    )                                                          AS prev_month_revenue,
    ROUND(
        (total_revenue - LAG(total_revenue) OVER (
            PARTITION BY plan_type ORDER BY sales_month
        )) * 100.0
        / NULLIF(LAG(total_revenue) OVER (
            PARTITION BY plan_type ORDER BY sales_month
        ), 0),
        2
    )                                                          AS mom_revenue_growth_pct,
    -- MoM加入者増減
    active_subscribers - LAG(active_subscribers) OVER (
        PARTITION BY plan_type ORDER BY sales_month
    )                                                          AS mom_subscriber_change
FROM gold.sales_per_plan
ORDER BY sales_month DESC, plan_type
""")
print("✅ v_revenue_trend 作成完了")

# COMMAND ----------

# MAGIC %md
# MAGIC ### View 3: Free→有料 転換ファネル
# MAGIC **用途**: Databricks SQL Dashboard — 「転換分析」ページ
# MAGIC **利用者**: グロースチーム・プロダクトマネージャー
# MAGIC **目的**: 転換率の把握と転換障壁の特定

# COMMAND ----------

spark.sql("""
CREATE OR REPLACE VIEW serving.v_conversion_funnel
COMMENT 'Free→有料転換ファネル — 月次転換率・解約クリック率の推移'
AS
SELECT
    kpi_date                                                                          AS funnel_date,
    DATE_TRUNC('MM', kpi_date)                                                        AS funnel_month,
    total_users,
    paid_users,
    free_users,
    cancel_click_count,
    failed_payment_count,
    -- 転換率: 全ユーザーに占める有料ユーザー比率
    ROUND(paid_users * 100.0 / NULLIF(total_users, 0), 2)                             AS signup_to_paid_rate_pct,
    -- 解約クリック率: 有料ユーザーに占める解約クリック比率
    ROUND(cancel_click_count * 100.0 / NULLIF(paid_users, 0), 2)                      AS cancel_click_rate_pct,
    -- 決済失敗率: 有料ユーザーに占める決済失敗比率
    ROUND(failed_payment_count * 100.0 / NULLIF(paid_users, 0), 2)                    AS failed_payment_rate_pct
FROM gold.daily_kpi
ORDER BY kpi_date DESC
""")
print("✅ v_conversion_funnel 作成完了")

# COMMAND ----------

# MAGIC %md
# MAGIC ### View 4: プラン別健全性スコアボード
# MAGIC **用途**: Databricks SQL Dashboard — 「プラン健全性」ページ
# MAGIC **利用者**: 経営層・プロダクトマネージャー
# MAGIC **目的**: 問題プランの早期特定（🔴=即時対応、🟡=要注視、🟢=正常）

# COMMAND ----------

spark.sql("""
CREATE OR REPLACE VIEW serving.v_plan_health
COMMENT 'プラン別健全性スコアボード — 解約リスク・決済失敗率をプラン単位で集計'
AS
WITH plan_stats AS (
    SELECT
        plan_type,
        COUNT(DISTINCT user_id)                                        AS total_paid_users,
        SUM(CASE WHEN churn_risk_flag = TRUE THEN 1 ELSE 0 END)        AS churn_risk_count,
        AVG(total_failed_payments)                                     AS avg_failed_payments,
        SUM(total_failed_payments)                                     AS total_failed_payments,
        SUM(CASE WHEN has_recent_cancel_click = TRUE THEN 1 ELSE 0 END) AS cancel_click_users
    FROM gold.failed_payment_user
    GROUP BY plan_type
)
SELECT
    plan_type,
    total_paid_users,
    churn_risk_count,
    ROUND(churn_risk_count * 100.0 / NULLIF(total_paid_users, 0), 2)   AS churn_risk_rate_pct,
    cancel_click_users,
    ROUND(cancel_click_users * 100.0 / NULLIF(total_paid_users, 0), 2) AS cancel_click_rate_pct,
    ROUND(avg_failed_payments, 2)                                      AS avg_failed_payment_count,
    total_failed_payments,
    -- 健全性判定 (Databricks SQL Dashboard のカラー表示に対応)
    CASE
        WHEN churn_risk_count * 100.0 / NULLIF(total_paid_users, 0) >= 20 THEN '🔴 Critical'
        WHEN churn_risk_count * 100.0 / NULLIF(total_paid_users, 0) >= 10 THEN '🟡 Warning'
        ELSE '🟢 Healthy'
    END                                                                AS health_status
FROM plan_stats
ORDER BY churn_risk_rate_pct DESC
""")
print("✅ v_plan_health 作成完了")

# COMMAND ----------

# MAGIC %md
# MAGIC ### View 5: CSチーム向け解約リスクアクションリスト
# MAGIC **用途**: Databricks SQL Dashboard — 「CSアクションリスト」ページ + **SQL Alerts トリガー元**
# MAGIC **利用者**: カスタマーサクセスチーム
# MAGIC **目的**: 解約リスクユーザーを優先度付きでリスト化し、CSが早期アクションを取れるようにする
# MAGIC **Alertsとの連携**: `churn_risk_flag = true` のレコード数 > 0 で Slack/Email 通知

# COMMAND ----------

spark.sql("""
CREATE OR REPLACE VIEW serving.v_churn_risk_action_list
COMMENT 'CSチーム向け解約リスクアクションリスト — SQL Alerts の通知トリガーとしても使用'
AS
SELECT
    user_id,
    plan_type,
    total_failed_payments,
    latest_payment_status,
    latest_payment_date,
    has_recent_cancel_click,
    churn_risk_flag,
    -- アクション優先度 (CSチームがトリアージに使用)
    CASE
        WHEN churn_risk_flag = TRUE AND has_recent_cancel_click = TRUE
            THEN '🔴 P0 — 即時コンタクト (決済失敗+解約クリック確認済)'
        WHEN churn_risk_flag = TRUE AND has_recent_cancel_click = FALSE
            THEN '🟡 P1 — 今週中にフォロー (決済失敗のみ)'
        WHEN churn_risk_flag = FALSE AND has_recent_cancel_click = TRUE
            THEN '🟠 P2 — 今月中にフォロー (解約クリックのみ)'
        ELSE '🟢 P3 — 定期モニタリング'
    END                                AS action_priority,
    -- 決済失敗パターン (CSのアプローチ判断に使用)
    CASE
        WHEN total_failed_payments >= 3 THEN '繰り返し失敗 (カード情報更新を促す)'
        WHEN total_failed_payments = 2  THEN '複数回失敗 (支払い方法変更を提案)'
        WHEN total_failed_payments = 1  THEN '初回失敗 (一時的エラーの可能性)'
        ELSE '決済失敗なし'
    END                                AS failure_pattern,
    -- CSノート用: 最終決済からの経過日数
    DATEDIFF(CURRENT_DATE(), latest_payment_date) AS days_since_last_payment
FROM gold.failed_payment_user
ORDER BY
    churn_risk_flag DESC,
    has_recent_cancel_click DESC,
    total_failed_payments DESC
""")
print("✅ v_churn_risk_action_list 作成完了")

# COMMAND ----------

# MAGIC %md
# MAGIC ### View 6: データ品質モニタリングダッシュボード
# MAGIC **用途**: Databricks SQL Dashboard — 「データ品質」ページ
# MAGIC **利用者**: データエンジニア・分析チーム
# MAGIC **目的**: Silver Layer への昇格可否判定と品質劣化の早期検知

# COMMAND ----------

spark.sql("""
CREATE OR REPLACE VIEW serving.v_data_quality_monitor
COMMENT 'データ品質モニタリング — Silver Layer昇格可否と品質劣化の早期検知'
AS
SELECT
    run_date,
    source_table,
    check_name,
    total_records,
    issue_count,
    ROUND(issue_rate_pct, 2)                                    AS issue_rate_pct,
    -- 品質ステータス (Databricks SQL のカラー条件付き書式に対応)
    CASE
        WHEN issue_rate_pct >= 10 THEN '🔴 Major   — 即時調査が必要'
        WHEN issue_rate_pct >= 3  THEN '⚠️  Warning — 要監視'
        ELSE '✅ Normal  — 正常範囲内'
    END                                                         AS quality_status,
    -- Silver Layer 昇格可否 (issue_rate >= 10% は昇格ブロック推奨)
    CASE
        WHEN issue_rate_pct >= 10 THEN '🚫 昇格ブロック推奨'
        ELSE '✅ 昇格可'
    END                                                         AS silver_promotion_gate
FROM gold.data_quality_summary
ORDER BY run_date DESC, issue_rate_pct DESC
""")
print("✅ v_data_quality_monitor 作成完了")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Databricks SQL Alerts 設定 (PySpark経由でSQLガイダンス生成)
# MAGIC
# MAGIC Databricks SQL Alerts は Databricks SQL UI から設定する。
# MAGIC 以下は設定手順とクエリを出力する。

# COMMAND ----------

alert_definitions = [
    {
        "name": "🔴 [CS Alert] 解約リスクユーザー検知",
        "purpose": "churn_risk_flagが立ったユーザーをCSチームにSlack/Email通知",
        "trigger_condition": "COUNT(*) > 0",
        "notification_target": "CSチーム Slack #cs-alerts チャンネル",
        "frequency": "1時間ごと",
        "query": """
-- Databricks SQL Alerts 設定クエリ (1)
-- Alert名: [CS] 解約リスクユーザー検知
-- トリガー条件: COUNT(*) > 0
-- 通知先: CSチーム Slack #cs-alerts
SELECT COUNT(*) AS churn_risk_user_count
FROM serving.v_churn_risk_action_list
WHERE churn_risk_flag = TRUE
  AND action_priority LIKE '%P0%'  -- P0 (最高優先) のみ即時通知
"""
    },
    {
        "name": "⚠️  [Data] データ品質劣化アラート",
        "purpose": "issue_rate_pct >= 10% のDQチェックを検知してデータエンジニアに通知",
        "trigger_condition": "COUNT(*) > 0",
        "notification_target": "データエンジニア Email",
        "frequency": "日次 (Gold Layer更新後)",
        "query": """
-- Databricks SQL Alerts 設定クエリ (2)
-- Alert名: [Data] データ品質劣化アラート
-- トリガー条件: COUNT(*) > 0
-- 通知先: データエンジニア Email
SELECT COUNT(*) AS critical_dq_count
FROM serving.v_data_quality_monitor
WHERE issue_rate_pct >= 10
  AND run_date = CURRENT_DATE()
"""
    },
    {
        "name": "📉 [Biz] 有料転換率低下アラート",
        "purpose": "paid_ratio_pctが前日比で2ポイント以上低下した場合に経営層へ通知",
        "trigger_condition": "COUNT(*) > 0",
        "notification_target": "経営層 Email",
        "frequency": "日次",
        "query": """
-- Databricks SQL Alerts 設定クエリ (3)
-- Alert名: [Biz] 有料転換率低下アラート
-- トリガー条件: COUNT(*) > 0
-- 通知先: 経営層 Email
SELECT COUNT(*) AS conversion_drop_days
FROM (
    SELECT
        kpi_date,
        paid_ratio_pct,
        LAG(paid_ratio_pct) OVER (ORDER BY kpi_date) AS prev_paid_ratio_pct
    FROM serving.v_executive_daily_kpi
) t
WHERE kpi_date = CURRENT_DATE() - INTERVAL 1 DAY
  AND (prev_paid_ratio_pct - paid_ratio_pct) >= 2.0  -- 2ポイント以上の低下
"""
    },
]

print("=" * 60)
print("Databricks SQL Alerts 設定ガイド")
print("設定場所: Databricks SQL > Alerts > Create Alert")
print("=" * 60)

for i, alert in enumerate(alert_definitions, 1):
    print(f"\n{'─' * 60}")
    print(f"Alert {i}: {alert['name']}")
    print(f"  目的      : {alert['purpose']}")
    print(f"  通知先    : {alert['notification_target']}")
    print(f"  実行頻度  : {alert['frequency']}")
    print(f"  条件      : {alert['trigger_condition']}")
    print(f"  SQL Query :{alert['query']}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Databricks SQL Dashboard 設計ガイド
# MAGIC
# MAGIC **設定場所**: Databricks SQL > Dashboards > Create Dashboard
# MAGIC
# MAGIC ### ダッシュボード構成 (4ページ)
# MAGIC
# MAGIC #### Page 1: 全社KPI (経営層向け)
# MAGIC | ウィジェット | ビュー | 可視化タイプ |
# MAGIC |---|---|---|
# MAGIC | 有料ユーザー数推移 | v_executive_daily_kpi | Line Chart (kpi_date × paid_users) |
# MAGIC | 日次収益推移 | v_executive_daily_kpi | Bar Chart (kpi_date × daily_revenue) |
# MAGIC | 有料転換率 | v_executive_daily_kpi | Line Chart (kpi_date × paid_ratio_pct) |
# MAGIC | Net有料ユーザー増減 | v_executive_daily_kpi | Bar Chart (正=緑/負=赤) |
# MAGIC
# MAGIC #### Page 2: 売上分析 (PM向け)
# MAGIC | ウィジェット | ビュー | 可視化タイプ |
# MAGIC |---|---|---|
# MAGIC | プラン別月次収益 | v_revenue_trend | Stacked Bar (sales_month × plan_type) |
# MAGIC | MoM成長率 | v_revenue_trend | Line Chart (mom_revenue_growth_pct) |
# MAGIC | プラン健全性スコアボード | v_plan_health | Table (health_status カラー列) |
# MAGIC
# MAGIC #### Page 3: CSアクションリスト (CSチーム向け)
# MAGIC | ウィジェット | ビュー | 可視化タイプ |
# MAGIC |---|---|---|
# MAGIC | 解約リスクユーザーリスト | v_churn_risk_action_list | Table (action_priority でソート) |
# MAGIC | リスクユーザー数サマリー | v_churn_risk_action_list | Counter (churn_risk_flag=true COUNT) |
# MAGIC | 転換ファネル | v_conversion_funnel | Funnel Chart |
# MAGIC
# MAGIC #### Page 4: データ品質 (データエンジニア向け)
# MAGIC | ウィジェット | ビュー | 可視化タイプ |
# MAGIC |---|---|---|
# MAGIC | DQステータス一覧 | v_data_quality_monitor | Table (quality_status カラー列) |
# MAGIC | 品質エラー率推移 | v_data_quality_monitor | Line Chart (run_date × issue_rate_pct) |

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. 作成済みビュー一覧確認

# COMMAND ----------

print("=" * 60)
print("serving データベース — ビュー一覧")
print("=" * 60)

views_df = spark.sql("SHOW VIEWS IN serving")
views_df.show(truncate=False)

print("\n各ビューのスキーマ確認:")
view_names = [row["viewName"] for row in views_df.collect()]

for view_name in view_names:
    print(f"\n{'─' * 50}")
    print(f"📋 serving.{view_name}")
    spark.sql(f"DESCRIBE serving.{view_name}").show(truncate=False)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. 動作確認 — 各ビューのサンプルデータ

# COMMAND ----------

print("=" * 60)
print("動作確認: 各ビューのサンプルデータ")
print("=" * 60)

verification_queries = [
    ("v_executive_daily_kpi",    "SELECT * FROM serving.v_executive_daily_kpi LIMIT 5"),
    ("v_revenue_trend",          "SELECT * FROM serving.v_revenue_trend LIMIT 5"),
    ("v_conversion_funnel",      "SELECT funnel_date, signup_to_paid_rate_pct, cancel_click_rate_pct, failed_payment_rate_pct FROM serving.v_conversion_funnel LIMIT 5"),
    ("v_plan_health",            "SELECT * FROM serving.v_plan_health"),
    ("v_churn_risk_action_list", "SELECT user_id, plan_type, action_priority, failure_pattern FROM serving.v_churn_risk_action_list WHERE churn_risk_flag = TRUE"),
    ("v_data_quality_monitor",   "SELECT source_table, check_name, issue_rate_pct, quality_status, silver_promotion_gate FROM serving.v_data_quality_monitor"),
]

for view_name, query in verification_queries:
    print(f"\n{'─' * 50}")
    print(f"📊 {view_name}")
    spark.sql(query).show(truncate=False)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Step 5 完了サマリー

# COMMAND ----------

print("""
╔══════════════════════════════════════════════════════════════╗
║           Step 5: Serving Layer 構築完了                    ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  ✅ 選定サービス: Databricks SQL (SQL Warehouse)            ║
║     理由: 経営層ダッシュボード + CSアラート要件に最適       ║
║                                                              ║
║  ✅ 作成ビュー (serving データベース)                        ║
║     1. v_executive_daily_kpi     — 経営層KPIダッシュボード  ║
║     2. v_revenue_trend           — プラン別売上MoM分析      ║
║     3. v_conversion_funnel       — Free→有料転換ファネル    ║
║     4. v_plan_health             — プラン健全性スコアボード  ║
║     5. v_churn_risk_action_list  — CSアクションリスト       ║
║     6. v_data_quality_monitor    — DQモニタリング           ║
║                                                              ║
║  ✅ Gold Layer OPTIMIZE + ZORDER 適用済み                   ║
║     (SQL Warehouse クエリ応答速度を最大化)                  ║
║                                                              ║
║  📋 次のアクション (Databricks SQL UI)                      ║
║     1. SQL Warehouse を起動                                  ║
║     2. Dashboard を 4 ページ構成で作成                       ║
║     3. Alerts を 3 件設定 (CS/Data/Biz)                    ║
║     4. 経営層・CSチームに Dashboard URL を共有              ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝

Medallion Architecture 全ステップ完了:
  sample_src (生データ)
    └─▶ bronze (Raw Delta + メタデータ)
          └─▶ silver (品質修正済み)
                └─▶ gold (集計済みビジネス指標)
                      └─▶ serving (SQL Views)
                                └─▶ Databricks SQL Dashboard / Alerts
""")
