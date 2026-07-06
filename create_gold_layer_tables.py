"""
Cloudbox Gold層 表設計・空テーブル作成スクリプト（Databricks Free Edition想定）

Knowledge base の「ユーザーと各ユーザーの期待するデータ」に記載された
3ユーザー層 × 4データニーズに対応する Gold 表のみを作成する（それ以外は作らない）。

  経営層         : 日次のKPI（売上・転換率・解約傾向）を見たい
                   → gold_daily_kpi
  CS/セールス     : 決済失敗や解約リスクがあるユーザーのリストを見たい
                   → gold_at_risk_users
  データチーム    : データ品質課題を把握したい
                   → gold_data_quality_summary
  データチーム    : 将来的なMLモデルに使う基盤を用意したい
                   → gold_user_ml_features

CREATE TABLE ... USING DELTA のSQL DDLで表を作成する。
DataFrameのwriteでは NOT NULL 制約が保存時に失われてしまうため、
NOT NULL を実際にDeltaテーブルへ反映させるにはSQL DDLでの列定義が必要。
このスクリプトでは表定義（スキーマ）のみを確定し、空のDeltaテーブルとして保存する。
実データの投入（Silver層からの集計ETL）は別スクリプトで行う想定。
"""

# ──────────────────────────────────────────────
# 0. Gold スキーマ（データベース）の作成
# ──────────────────────────────────────────────

spark.sql("CREATE DATABASE IF NOT EXISTS gold")
spark.sql("USE gold")

print("データベース 'gold' を選択しました")


# ──────────────────────────────────────────────
# 1. gold_daily_kpi
#    粒度: 1行 = 集計日(kpi_date) × country_code × plan_type
#    目的: 経営層向け。日次の売上・新規/解約契約数から
#          売上推移・転換率・解約傾向を国/プラン単位で把握できるようにする
# ──────────────────────────────────────────────

spark.sql("""
CREATE TABLE IF NOT EXISTS gold.gold_daily_kpi (
  kpi_date                     DATE   NOT NULL COMMENT '集計対象日',
  country_code                 STRING NOT NULL COMMENT '国コード（正規化済みISO2、例:"JP"）',
  plan_type                    STRING NOT NULL COMMENT 'プラン種別(basic/pro/business)',
  new_subscriptions_count      BIGINT NOT NULL COMMENT '当日の新規契約件数（フリー→有料転換含む）',
  churned_subscriptions_count  BIGINT NOT NULL COMMENT '当日の解約件数',
  active_subscriptions_count   BIGINT NOT NULL COMMENT '当日時点の有効契約数',
  gross_revenue_amount         DOUBLE NOT NULL COMMENT '当日の売上金額（決済成功分の合計）',
  failed_payment_count         BIGINT NOT NULL COMMENT '当日の決済失敗件数',
  conversion_rate               DOUBLE COMMENT '転換率（新規契約数 ÷ 当日アクティブなフリーユーザー数、分母0はnull）',
  churn_rate                    DOUBLE COMMENT '解約率（解約数 ÷ 前日時点の有効契約数、分母0はnull）'
)
USING DELTA
COMMENT '経営層向け: 国/プラン別の日次KPI（売上・転換率・解約傾向）'
""")

print("gold_daily_kpi を作成しました（空テーブル）")


# ──────────────────────────────────────────────
# 2. gold_at_risk_users
#    粒度: 1行 = スナップショット日(snapshot_date) × user_id
#    目的: CS/セールス向け。決済失敗や解約兆候があるユーザーを
#          日次スナップショットとしてリスト化し、対応優先度を判断できるようにする
# ──────────────────────────────────────────────

spark.sql("""
CREATE TABLE IF NOT EXISTS gold.gold_at_risk_users (
  snapshot_date                 DATE   NOT NULL COMMENT 'リスト算出基準日',
  user_id                        STRING NOT NULL COMMENT 'ユーザーID',
  country_code                   STRING COMMENT '正規化済み国コード',
  plan_type                      STRING COMMENT '現在の契約プラン',
  last_payment_status            STRING COMMENT '直近の決済ステータス',
  consecutive_failed_payments    BIGINT NOT NULL COMMENT '連続決済失敗回数',
  days_since_last_login          BIGINT COMMENT '最終ログインからの経過日数（履歴が無い場合はnull）',
  cancel_click_count_30d         BIGINT NOT NULL COMMENT '直近30日間の解約クリックイベント数',
  churn_risk_level                STRING NOT NULL COMMENT '解約リスクレベル(low/medium/high)',
  risk_reason                     STRING COMMENT 'リスク判定理由（例:"決済失敗2回連続"）'
)
USING DELTA
COMMENT 'CS/セールス向け: 決済失敗・解約リスクユーザーの日次スナップショット'
""")

print("gold_at_risk_users を作成しました（空テーブル）")


# ──────────────────────────────────────────────
# 3. gold_data_quality_summary
#    粒度: 1行 = チェック実行日(check_date) × 対象Bronze表(source_table) × 品質チェック項目(quality_check_name)
#    目的: データチーム向け。Bronze層で発生している品質課題（null/重複/表記揺れ等）の
#          件数・割合を日次で追跡し、悪化/改善のトレンドを把握できるようにする
# ──────────────────────────────────────────────

spark.sql("""
CREATE TABLE IF NOT EXISTS gold.gold_data_quality_summary (
  check_date            DATE   NOT NULL COMMENT '品質チェック実行日',
  source_table           STRING NOT NULL COMMENT '対象のBronzeテーブル名',
  quality_check_name      STRING NOT NULL COMMENT '品質チェック項目名（例: null_user_id, duplicate_event_id）',
  total_record_count      BIGINT NOT NULL COMMENT 'チェック対象の総レコード数',
  failed_record_count     BIGINT NOT NULL COMMENT '品質課題に該当したレコード数',
  failed_record_ratio     DOUBLE COMMENT '該当割合（failed÷total、total=0はnull）',
  severity                 STRING COMMENT '深刻度(low/medium/high)'
)
USING DELTA
COMMENT 'データチーム向け: Bronze層データ品質課題の日次サマリー'
""")

print("gold_data_quality_summary を作成しました（空テーブル）")


# ──────────────────────────────────────────────
# 4. gold_user_ml_features
#    粒度: 1行 = 特徴量算出日(feature_date) × user_id
#    目的: データチーム向け。将来の解約予測MLモデル学習に利用できるよう、
#          ユーザー単位の行動・課金特徴量を日次スナップショットとして蓄積する基盤
# ──────────────────────────────────────────────

spark.sql("""
CREATE TABLE IF NOT EXISTS gold.gold_user_ml_features (
  feature_date               DATE   NOT NULL COMMENT '特徴量算出基準日',
  user_id                     STRING NOT NULL COMMENT 'ユーザーID',
  country_code                 STRING COMMENT '正規化済み国コード',
  signup_platform               STRING COMMENT '登録プラットフォーム',
  tenure_days                   BIGINT COMMENT '登録からの経過日数',
  current_plan_type             STRING COMMENT '現在の契約プラン（フリーの場合はnull）',
  total_logins_30d             BIGINT NOT NULL COMMENT '直近30日間のログイン回数',
  total_feature_use_30d        BIGINT NOT NULL COMMENT '直近30日間の機能利用回数',
  upgrade_click_count_30d      BIGINT NOT NULL COMMENT '直近30日間のアップグレードクリック回数',
  cancel_click_count_30d       BIGINT NOT NULL COMMENT '直近30日間の解約クリック回数',
  failed_payment_count_90d     BIGINT NOT NULL COMMENT '直近90日間の決済失敗回数',
  total_revenue_to_date        DOUBLE NOT NULL COMMENT '累計売上金額',
  is_churned_label              BOOLEAN COMMENT '解約済みか（学習用教師ラベル、未確定はnull）'
)
USING DELTA
COMMENT 'データチーム向け: 将来のML解約予測モデル用ユーザー特徴量ストア'
""")

print("gold_user_ml_features を作成しました（空テーブル）")

print("\n=== Gold層 空テーブルの作成完了 ===")
