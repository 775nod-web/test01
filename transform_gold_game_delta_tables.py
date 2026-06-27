# Databricks ノートブック用
# Silver テーブルを集計して Gold レイヤーとして保存する
#
# 作成テーブル：
#   ① gold_kpi_daily       : 経営層向け KPI ダッシュボード用（日別・タイトル別集計）
#   ② gold_churn_features  : ML エンジニア向けチャーン予測用特徴量（ユーザー別集計）

%python
from pyspark.sql import functions as F

# ──────────────────────────────────────────────
# 0. スキーマの作成・切り替え
# ──────────────────────────────────────────────

# スキーマが存在しない場合のみ作成（冪等性を確保）
spark.sql("CREATE DATABASE IF NOT EXISTS interview_prep")
spark.sql("USE interview_prep")

print("スキーマ 'interview_prep' を選択しました\n")


# ──────────────────────────────────────────────
# Silver テーブルの読み込み
# ──────────────────────────────────────────────

# クレンジング済みの Silver テーブルを読み込む
df_silver_gameplay = spark.table("interview_prep.silver_gameplay_log")
df_silver_purchase = spark.table("interview_prep.silver_purchase")
df_silver_user     = spark.table("interview_prep.silver_user_master")

print(f"Silver 読み込み完了:")
print(f"  silver_gameplay_log : {df_silver_gameplay.count():,} 件")
print(f"  silver_purchase     : {df_silver_purchase.count():,} 件")
print(f"  silver_user_master  : {df_silver_user.count():,} 件\n")


# ══════════════════════════════════════════════
# ① gold_kpi_daily
#    経営層向け KPI ダッシュボード用
#    groupBy：event_date・title_id
#    集計：DAU / 総プレイ時間 / 総課金額
# ══════════════════════════════════════════════

# -- gameplay から DAU・総プレイ時間を集計 --
df_gameplay_daily = (
    df_silver_gameplay
    .groupBy("event_date", "title_id")
    .agg(
        # DAU：日付・タイトルごとのユニークユーザー数
        F.countDistinct("user_id").alias("dau"),
        # 総プレイ時間（秒）：日付・タイトルごとの合計プレイ秒数
        F.sum("play_seconds").alias("total_play_seconds"),
    )
)

# -- purchase から日別・タイトル別の総課金額を集計 --
df_purchase_daily = (
    df_silver_purchase
    .withColumn(
        # purchase_ts から日付を抽出して gameplay の event_date と結合できるようにする
        "purchase_date", F.to_date(F.col("purchase_ts"))
    )
    .groupBy(
        F.col("purchase_date").alias("event_date"),   # gameplay と結合するためにリネーム
        "title_id"
    )
    .agg(
        # 総課金額（円）：日付・タイトルごとの合計金額
        F.sum("amount_jpy").alias("total_revenue_jpy"),
    )
)

# -- gameplay 集計と purchase 集計を event_date・title_id で結合 --
df_gold_kpi_daily = (
    df_gameplay_daily
    .join(
        df_purchase_daily,
        on=["event_date", "title_id"],
        how="left"   # 課金がない日でも gameplay の行は残す
    )
    # 課金がない日は 0 円で補完（NULL のままにしない）
    .withColumn(
        "total_revenue_jpy",
        F.coalesce(F.col("total_revenue_jpy"), F.lit(0))
    )
    # 経営層が見やすいよう日付・タイトル順に並び替え
    .orderBy("event_date", "title_id")
)

# 保存
(
    df_gold_kpi_daily
    .write
    .format("delta")                      # Delta Lake 形式で保存
    .mode("overwrite")                    # 既存テーブルを上書き（冪等実行を保証）
    .option("overwriteSchema", "true")    # スキーマ変更も上書き許可
    .saveAsTable("interview_prep.gold_kpi_daily")
)

kpi_count = spark.table("interview_prep.gold_kpi_daily").count()
print(f"gold_kpi_daily 保存完了: {kpi_count:,} 件")
spark.table("interview_prep.gold_kpi_daily").show(5, truncate=False)


# ══════════════════════════════════════════════
# ② gold_churn_features
#    ML エンジニア向けチャーン予測用特徴量
#    groupBy：user_id
#    集計：直近 30 日のプレイ日数 / 総プレイ時間 / 課金回数 / 課金総額
# ══════════════════════════════════════════════

# 直近 30 日の基準日：データ内の最大 event_ts を「現在」とみなす
max_ts = df_silver_gameplay.agg(F.max("event_ts")).collect()[0][0]

# 直近 30 日のウィンドウ開始日時（基準日 - 30 日）
window_start = max_ts - F.expr("INTERVAL 30 DAYS")   # Spark には直接使えないため下記で処理

from datetime import timedelta
window_start_dt = max_ts - timedelta(days=30)
print(f"\n特徴量集計ウィンドウ: {window_start_dt} ～ {max_ts}")

# -- gameplay を直近 30 日に絞り込んでユーザー別に集計 --
df_gameplay_features = (
    df_silver_gameplay
    # 直近 30 日のレコードのみ対象
    .filter(F.col("event_ts") >= F.lit(window_start_dt))
    .groupBy("user_id")
    .agg(
        # 直近 30 日のプレイ日数：ユニーク日数をカウント
        F.countDistinct(F.to_date("event_ts")).alias("play_days_last30"),
        # 直近 30 日の総プレイ時間（秒）
        F.sum("play_seconds").alias("total_play_seconds_last30"),
    )
)

# -- purchase を直近 30 日に絞り込んでユーザー別に集計 --
df_purchase_features = (
    df_silver_purchase
    # 直近 30 日のレコードのみ対象
    .filter(F.col("purchase_ts") >= F.lit(window_start_dt))
    .groupBy("user_id")
    .agg(
        # 直近 30 日の課金回数
        F.count("purchase_id").alias("purchase_count_last30"),
        # 直近 30 日の課金総額（円）
        F.sum("amount_jpy").alias("total_revenue_jpy_last30"),
    )
)

# -- silver_user_master を起点に gameplay・purchase の特徴量を結合 --
df_gold_churn_features = (
    df_silver_user
    .select("user_id")   # 特徴量テーブルのベースはユーザーマスター
    .join(df_gameplay_features, on="user_id", how="left")   # プレイ特徴量を付与
    .join(df_purchase_features, on="user_id", how="left")   # 課金特徴量を付与
    # 直近 30 日に活動がないユーザーは 0 で補完（NULL は ML モデルに悪影響）
    .withColumn("play_days_last30",          F.coalesce(F.col("play_days_last30"),          F.lit(0)))
    .withColumn("total_play_seconds_last30", F.coalesce(F.col("total_play_seconds_last30"), F.lit(0)))
    .withColumn("purchase_count_last30",     F.coalesce(F.col("purchase_count_last30"),     F.lit(0)))
    .withColumn("total_revenue_jpy_last30",  F.coalesce(F.col("total_revenue_jpy_last30"),  F.lit(0)))
    # ユーザー ID 順に並び替え
    .orderBy("user_id")
)

# 保存
(
    df_gold_churn_features
    .write
    .format("delta")                      # Delta Lake 形式で保存
    .mode("overwrite")                    # 既存テーブルを上書き
    .option("overwriteSchema", "true")    # スキーマ変更も上書き許可
    .saveAsTable("interview_prep.gold_churn_features")
)

churn_count = spark.table("interview_prep.gold_churn_features").count()
print(f"gold_churn_features 保存完了: {churn_count:,} 件")
spark.table("interview_prep.gold_churn_features").show(5, truncate=False)


# ──────────────────────────────────────────────
# 保存結果サマリー
# ──────────────────────────────────────────────

print("\n" + "=" * 55)
print("=== Gold レイヤー 保存完了サマリー ===")
print("=" * 55)
print(f"  gold_kpi_daily      : {kpi_count:>6,} 件  （日別×タイトル別 KPI）")
print(f"  gold_churn_features : {churn_count:>6,} 件  （ユーザー別チャーン予測特徴量）")
print("=" * 55)
print("\nカラム構成：")
print("  gold_kpi_daily      : event_date / title_id / dau / total_play_seconds / total_revenue_jpy")
print("  gold_churn_features : user_id / play_days_last30 / total_play_seconds_last30")
print("                        / purchase_count_last30 / total_revenue_jpy_last30")
