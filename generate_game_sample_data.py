# Databricks ノートブック用
# モバイルゲーム分析基盤 サンプルデータ生成スクリプト
#
# 生成するデータ：
#   - df_gameplay_log  : ゲームプレイログ（リアルタイム取り込み想定）
#   - df_purchase      : 課金データ（リアルタイム取り込み想定）
#   - df_user_master   : ユーザーマスター（日次バッチ想定）
#
# 意図的に含むデータ品質課題：
#   1. プレイログの event_type に一部 Null
#   2. タイトルをまたいで同一 user_id が使用される（名寄せ前提）
#
# 動作確認環境：Databricks Free Edition（Unity Catalog 不使用・Hive メタストア）

from pyspark.sql import Row
from pyspark.sql.types import (
    StructType, StructField,
    StringType, IntegerType, LongType, DoubleType, TimestampType
)
from datetime import datetime, timedelta
import random

random.seed(42)

# ──────────────────────────────────────────────
# 定数定義
# ──────────────────────────────────────────────

TITLE_IDS   = ["title_001", "title_002", "title_003"]
EVENT_TYPES = ["battle_start", "battle_end", "item_purchase", "level_up", "login", "logout"]
COUNTRIES   = ["JP", "US", "KR", "TW", "SG"]
DEVICES     = ["iOS", "Android"]

# タイトルをまたいで同じ user_id が使われるケースを表現するため、
# 全タイトル共通の user_id プールを用意する（名寄せ課題の再現）
USER_POOL_SIZE = 200   # 全ユーザープール
ACTIVE_USERS   = 120   # マスターに登録されているユーザー数

BASE_TS = datetime(2025, 1, 1, 0, 0, 0)


def rand_ts(days_range: int = 90) -> datetime:
    """BASE_TS から days_range 日以内のランダムなタイムスタンプを返す"""
    return BASE_TS + timedelta(
        seconds=random.randint(0, days_range * 86400)
    )


# ──────────────────────────────────────────────
# 1. ユーザーマスター生成（120件）
#    ※ user_id は "u_0001" ～ "u_0120" の形式
#    ※ 一部ユーザーは複数タイトルにまたがって存在する（下記プレイログ参照）
# ──────────────────────────────────────────────

user_master_rows = []
for i in range(1, ACTIVE_USERS + 1):
    user_master_rows.append(Row(
        user_id         = f"u_{i:04d}",
        registration_dt = (BASE_TS - timedelta(days=random.randint(1, 365))).date().isoformat(),
        country         = random.choice(COUNTRIES),
        device          = random.choice(DEVICES),
    ))

user_master_schema = StructType([
    StructField("user_id",         StringType(),  nullable=False),
    StructField("registration_dt", StringType(),  nullable=True),   # DATE を文字列で保持（Bronze 生データ）
    StructField("country",         StringType(),  nullable=True),
    StructField("device",          StringType(),  nullable=True),
])

df_user_master = spark.createDataFrame(user_master_rows, schema=user_master_schema)

print(f"df_user_master: {df_user_master.count():,} 件")
df_user_master.show(5, truncate=False)


# ──────────────────────────────────────────────
# 2. ゲームプレイログ生成（3,000件）
#
#    データ品質課題を意図的に混入：
#      A) event_type が Null のレコードを約5%混入
#      B) user_id の範囲を u_0001 ～ u_0200 に広げ、
#         マスター未登録ユーザー（u_0121 ～ u_0200）も含める
#         → タイトルをまたいだ名寄せが必要なことを示す
# ──────────────────────────────────────────────

gameplay_log_rows = []
for i in range(1, 3001):
    # u_0001 ～ u_0200（マスター外ユーザーも含む → 名寄せ課題）
    uid = f"u_{random.randint(1, USER_POOL_SIZE):04d}"
    title = random.choice(TITLE_IDS)
    ts = rand_ts(90)

    # 約5%の確率で event_type を Null にする（データ品質課題 A）
    event_type = None if random.random() < 0.05 else random.choice(EVENT_TYPES)

    gameplay_log_rows.append(Row(
        log_id       = f"log_{i:06d}",
        user_id      = uid,
        title_id     = title,
        play_seconds = random.randint(30, 3600),
        event_type   = event_type,              # Null が混入する可能性あり
        event_ts     = ts,
        ingest_ts    = ts + timedelta(seconds=random.randint(1, 30)),  # ストリーミング取り込み遅延
    ))

gameplay_log_schema = StructType([
    StructField("log_id",       StringType(),   nullable=False),
    StructField("user_id",      StringType(),   nullable=True),
    StructField("title_id",     StringType(),   nullable=True),
    StructField("play_seconds", IntegerType(),  nullable=True),
    StructField("event_type",   StringType(),   nullable=True),   # Null 混入あり
    StructField("event_ts",     TimestampType(),nullable=True),
    StructField("ingest_ts",    TimestampType(),nullable=True),
])

df_gameplay_log = spark.createDataFrame(gameplay_log_rows, schema=gameplay_log_schema)

null_count = df_gameplay_log.filter("event_type IS NULL").count()
print(f"df_gameplay_log: {df_gameplay_log.count():,} 件 （event_type Null: {null_count} 件）")
df_gameplay_log.show(5, truncate=False)


# ──────────────────────────────────────────────
# 3. 課金データ生成（800件）
#
#    ※ user_id の範囲はプレイログと同じ（u_0001 ～ u_0200）
#    ※ 課金ユーザーはヘビーユーザー寄りに偏らせる（現実に近い分布）
# ──────────────────────────────────────────────

# ヘビー課金ユーザー（上位20%が80%の売上）を再現するため
# user_id に重みをつけてサンプリング
heavy_users = [f"u_{i:04d}" for i in range(1, 41)]     # u_0001 ～ u_0040 をヘビー課金層とする
light_users = [f"u_{i:04d}" for i in range(41, USER_POOL_SIZE + 1)]

purchase_rows = []
for i in range(1, 801):
    # 80% の確率でヘビー課金ユーザーから選択（パレートの法則）
    uid = random.choice(heavy_users) if random.random() < 0.80 else random.choice(light_users)
    ts  = rand_ts(90)

    # 課金金額：120円 / 480円 / 960円 / 1920円 / 4800円 の5段階
    amount = random.choice([120, 480, 960, 1920, 4800])

    purchase_rows.append(Row(
        purchase_id = f"pch_{i:06d}",
        user_id     = uid,
        title_id    = random.choice(TITLE_IDS),
        amount_jpy  = amount,
        purchase_ts = ts,
        ingest_ts   = ts + timedelta(seconds=random.randint(1, 60)),
    ))

purchase_schema = StructType([
    StructField("purchase_id",  StringType(),    nullable=False),
    StructField("user_id",      StringType(),    nullable=True),
    StructField("title_id",     StringType(),    nullable=True),
    StructField("amount_jpy",   IntegerType(),   nullable=True),
    StructField("purchase_ts",  TimestampType(), nullable=True),
    StructField("ingest_ts",    TimestampType(), nullable=True),
])

df_purchase = spark.createDataFrame(purchase_rows, schema=purchase_schema)

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
