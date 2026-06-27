# Databricks ノートブック用
# モバイルゲーム分析基盤 サンプルデータ生成スクリプト
#
# 生成するデータ：
#   - df_gameplay_log  : ゲームプレイログ（3,000件）
#   - df_purchase      : 課金データ（800件）
#   - df_user_master   : ユーザーマスター（120件）
#
# 意図的に含むデータ品質課題：
#   1. プレイログの event_type に一部 Null
#   2. タイトルをまたいで同一 user_id が使用される（名寄せ前提）
#
# Free Edition 対応：spark.range() + Spark SQL 式で分散生成し
# ドライバーへの大量データ集約を回避する

from pyspark.sql import functions as F

# ──────────────────────────────────────────────
# 共通設定
# ──────────────────────────────────────────────

BASE_TS = "2025-01-01 00:00:00"   # データ開始日時
RANGE_SECONDS = 90 * 86400        # 90日分の秒数


# ──────────────────────────────────────────────
# 1. ユーザーマスター（120件）
# ──────────────────────────────────────────────

df_user_master = (
    spark.range(1, 121)   # id: 1 ～ 120
    .select(
        F.format_string("u_%04d", F.col("id")).alias("user_id"),
        F.date_sub(
            F.to_date(F.lit(BASE_TS)),
            (F.rand(seed=1) * 364 + 1).cast("int")
        ).cast("string").alias("registration_dt"),
        F.element_at(
            F.array(F.lit("JP"), F.lit("US"), F.lit("KR"), F.lit("TW"), F.lit("SG")),
            (F.rand(seed=2) * 5 + 1).cast("int")
        ).alias("country"),
        F.element_at(
            F.array(F.lit("iOS"), F.lit("Android")),
            (F.rand(seed=3) * 2 + 1).cast("int")
        ).alias("device"),
    )
)

print(f"df_user_master: {df_user_master.count():,} 件")
df_user_master.show(5, truncate=False)


# ──────────────────────────────────────────────
# 2. ゲームプレイログ（3,000件）
#
#    品質課題：
#      A) event_type が Null のレコードを約5%混入
#      B) user_id を u_0001～u_0200 に広げ、
#         マスター未登録ユーザーも含める（名寄せ課題）
# ──────────────────────────────────────────────

df_gameplay_log = (
    spark.range(1, 3001)
    .select(
        F.format_string("log_%06d", F.col("id")).alias("log_id"),
        # user_id: u_0001 ～ u_0200（マスター外も含む）
        F.format_string("u_%04d", (F.rand(seed=10) * 200 + 1).cast("int")).alias("user_id"),
        F.element_at(
            F.array(F.lit("title_001"), F.lit("title_002"), F.lit("title_003")),
            (F.rand(seed=11) * 3 + 1).cast("int")
        ).alias("title_id"),
        (F.rand(seed=12) * (3600 - 30) + 30).cast("int").alias("play_seconds"),
        # event_type: 約5%を Null にする（品質課題 A）
        F.when(
            F.rand(seed=13) < 0.05,
            F.lit(None).cast("string")
        ).otherwise(
            F.element_at(
                F.array(
                    F.lit("battle_start"), F.lit("battle_end"),
                    F.lit("item_purchase"), F.lit("level_up"),
                    F.lit("login"), F.lit("logout")
                ),
                (F.rand(seed=14) * 6 + 1).cast("int")
            )
        ).alias("event_type"),
        # event_ts: BASE_TS から 90日以内のランダムなタイムスタンプ
        (
            F.to_timestamp(F.lit(BASE_TS)).cast("long")
            + (F.rand(seed=15) * RANGE_SECONDS).cast("long")
        ).cast("timestamp").alias("event_ts"),
    )
    .withColumn(
        "ingest_ts",
        (F.col("event_ts").cast("long") + (F.rand(seed=16) * 30 + 1).cast("long"))
        .cast("timestamp")
    )
)

null_count = df_gameplay_log.filter("event_type IS NULL").count()
print(f"df_gameplay_log: {df_gameplay_log.count():,} 件 （event_type Null: {null_count} 件）")
df_gameplay_log.show(5, truncate=False)


# ──────────────────────────────────────────────
# 3. 課金データ（800件）
#    ヘビー課金ユーザー（u_0001～u_0040）を80%の確率で選択
# ──────────────────────────────────────────────

AMOUNT_LIST = F.array(
    F.lit(120), F.lit(480), F.lit(960), F.lit(1920), F.lit(4800)
)

df_purchase = (
    spark.range(1, 801)
    .select(
        F.format_string("pch_%06d", F.col("id")).alias("purchase_id"),
        # ヘビー課金層（u_0001～u_0040）を 80% の確率で選択
        F.when(
            F.rand(seed=20) < 0.80,
            F.format_string("u_%04d", (F.rand(seed=21) * 40 + 1).cast("int"))
        ).otherwise(
            F.format_string("u_%04d", (F.rand(seed=22) * 160 + 41).cast("int"))
        ).alias("user_id"),
        F.element_at(
            F.array(F.lit("title_001"), F.lit("title_002"), F.lit("title_003")),
            (F.rand(seed=23) * 3 + 1).cast("int")
        ).alias("title_id"),
        F.element_at(AMOUNT_LIST, (F.rand(seed=24) * 5 + 1).cast("int")).alias("amount_jpy"),
        (
            F.to_timestamp(F.lit(BASE_TS)).cast("long")
            + (F.rand(seed=25) * RANGE_SECONDS).cast("long")
        ).cast("timestamp").alias("purchase_ts"),
    )
    .withColumn(
        "ingest_ts",
        (F.col("purchase_ts").cast("long") + (F.rand(seed=26) * 60 + 1).cast("long"))
        .cast("timestamp")
    )
)

print(f"df_purchase: {df_purchase.count():,} 件")
df_purchase.show(5, truncate=False)


# ──────────────────────────────────────────────
# 4. 生成サマリー
# ──────────────────────────────────────────────

print("\n" + "=" * 50)
print("=== サンプルデータ生成サマリー ===")
print("=" * 50)
print(f"  df_user_master  : {df_user_master.count():>6,} 件")
print(f"  df_gameplay_log : {df_gameplay_log.count():>6,} 件  （event_type Null: {null_count} 件）")
print(f"  df_purchase     : {df_purchase.count():>6,} 件")
print("=" * 50)
print("\n意図的に含むデータ品質課題：")
print("  [1] df_gameplay_log.event_type に約5%の Null が混入")
print("  [2] user_id が u_0001～u_0200 の範囲にあり、")
print("      マスター登録済み（u_0001～u_0120）と未登録（u_0121～u_0200）が混在")
print("      → タイトルをまたいだ分析には Silver 層での名寄せが必要")
