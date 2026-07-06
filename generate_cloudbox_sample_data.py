"""
Cloudbox サンプルデータ生成スクリプト（Bronze層／Databricks Free Edition想定）

対象データソース（3表のみ。データソースに存在しない表は作成しない）
1. bronze_users         ユーザーマスター            60件
                        品質課題：country_code表記揺れ 8件
2. bronze_subscriptions サブスクリプションデータ     100件
                        品質課題：user_id null 3件／user masterに存在しないuser_id 3件／
                                  payment_dateフォーマット不整合 10件／
                                  amountが0または負値 4件／payment_statusが想定外の値 5件
3. bronze_user_events   ユーザーアクションイベントログ 300件
                        品質課題：user_id null 6件／user masterに存在しないuser_id 6件／
                                  event_idの重複到着 8件（4組）／イベントの遅延到着 10件

設計方針:
- ビジネス上「フリーユーザーがなかなか有料転換できていない」課題を再現するため、
  bronze_subscriptions には有料プラン（basic/pro/business）に転換したユーザーのみが登場する。
  bronze_users に存在するがbronze_subscriptionsに登場しないユーザー＝フリーユーザー。
- Databricks Free Edition のノートブックで実行される前提のため、
  SparkSession.builder は呼ばない（spark はクラスターから自動注入される）。
"""

from pyspark.sql import Row
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType, DateType, TimestampType
)
import random
from datetime import date, datetime, timedelta

# 再現性のためのシード固定
random.seed(42)


# ──────────────────────────────────────────────
# ユーティリティ
# ──────────────────────────────────────────────

def random_date(start: date, end: date) -> date:
    """start〜end の範囲でランダムな日付を返す"""
    delta = (end - start).days
    if delta <= 0:
        return start
    return start + timedelta(days=random.randint(0, delta))


def random_datetime(start: datetime, end: datetime) -> datetime:
    """start〜end の範囲でランダムな日時を返す"""
    delta_seconds = int((end - start).total_seconds())
    return start + timedelta(seconds=random.randint(0, delta_seconds))


# ──────────────────────────────────────────────
# 1. ユーザーマスター（bronze_users）60件
#    品質課題：country_code の表記揺れ（jp/jpn/Japan/JAPAN）8件
# ──────────────────────────────────────────────

# ユーザーマスターのスキーマ定義
user_schema = StructType([
    StructField("user_id",         StringType(), nullable=False),  # ユーザーID（主キー）
    StructField("user_name",       StringType(), nullable=True),   # ユーザー表示名
    StructField("email",           StringType(), nullable=True),   # メールアドレス
    StructField("country_code",    StringType(), nullable=True),   # 居住国コード（品質課題：表記揺れ）
    StructField("signup_platform", StringType(), nullable=True),   # 登録プラットフォーム(web/ios/android)
    StructField("signup_date",     DateType(),   nullable=True),   # 登録日
])

COUNTRIES = ["JP", "US", "GB", "DE", "FR", "IN", "BR", "AU", "KR", "CA"]
PLATFORMS = ["web", "ios", "android"]
JP_VARIANTS = ["jp", "jpn", "Japan", "JAPAN"]  # 本来は "JP" に統一されるべき表記揺れ

SIGNUP_START = date(2023, 1, 1)
SIGNUP_END = date(2024, 12, 31)

TOTAL_USERS = 60
JP_VARIANT_COUNT = 8  # country_code 表記揺れの対象件数

jp_variant_indices = set(random.sample(range(1, TOTAL_USERS + 1), JP_VARIANT_COUNT))

user_rows = []
for i in range(1, TOTAL_USERS + 1):
    user_id = f"U{str(i).zfill(4)}"  # U0001〜U0060
    country = random.choice(COUNTRIES)
    if i in jp_variant_indices:
        country = random.choice(JP_VARIANTS)  # ← 品質課題：country_codeの表記揺れ

    user_rows.append(Row(
        user_id=user_id,
        user_name=f"user_{i:04d}",
        email=f"user{i:04d}@example.com",
        country_code=country,
        signup_platform=random.choice(PLATFORMS),
        signup_date=random_date(SIGNUP_START, SIGNUP_END),
    ))

df_users = spark.createDataFrame(user_rows, schema=user_schema)

print(f"=== ユーザーマスター（{df_users.count()}件） ===")
df_users.show(10, truncate=False)

# 後続のFK生成で使用（正規のuser_id一覧、signup_dateルックアップ）
valid_user_ids = [r.user_id for r in df_users.select("user_id").collect()]
signup_date_lookup = {r.user_id: r.signup_date for r in df_users.select("user_id", "signup_date").collect()}


# ──────────────────────────────────────────────
# 2. サブスクリプションデータ（bronze_subscriptions）100件
#    有料プラン（basic/pro/business）に転換したユーザーのみが登場する
#    品質課題：
#      - user_idがnull                              3件
#      - user masterに存在しないuser_id               3件
#      - payment_dateのフォーマット不整合（文字列型）    10件
#      - amountが0または負値                          4件
#      - payment_statusが想定外の値                    5件
# ──────────────────────────────────────────────

subscription_schema = StructType([
    StructField("subscription_id",     StringType(), nullable=False),  # サブスクリプションID（主キー）
    StructField("user_id",             StringType(), nullable=True),   # ユーザーID（外部キー。品質課題によりnullable）
    StructField("plan_type",           StringType(), nullable=True),   # 契約プラン(basic/pro/business)
    StructField("payment_status",      StringType(), nullable=True),   # 決済ステータス（品質課題：想定外の値混入）
    StructField("amount",              DoubleType(), nullable=True),   # 決済金額（品質課題：0/負値混入）
    # payment_date は本来 Date であるべきだが、ソースシステムの都合で文字列のまま連携され
    # フォーマットが揺れる、という品質課題を表現するためあえて StringType にしている
    StructField("payment_date",        StringType(), nullable=True),
    StructField("contract_start_date", DateType(),   nullable=True),   # 契約開始日
    StructField("contract_end_date",   DateType(),   nullable=True),   # 契約終了日（解約時のみ設定、継続中はnull）
])

PLANS = ["basic", "pro", "business"]
PLAN_PRICE = {"basic": 980.0, "pro": 2980.0, "business": 9800.0}
VALID_PAYMENT_STATUSES = ["success", "failed", "pending", "refunded"]
INVALID_PAYMENT_STATUSES = ["ERROR", "unknown", "", "N/A", "PENDING_XXX"]  # 品質課題：想定外の値

CONTRACT_START = date(2023, 1, 1)
CONTRACT_END_RANGE = date(2024, 12, 31)

TOTAL_SUBS = 100
NULL_USERID_SUB_COUNT = 3
ORPHAN_USERID_SUB_COUNT = 3
BAD_DATE_FORMAT_COUNT = 10
BAD_AMOUNT_COUNT = 4
BAD_STATUS_COUNT = 5

# 品質課題を注入する行番号をシャッフルして重複なく割り当てる
sub_indices = list(range(1, TOTAL_SUBS + 1))
random.shuffle(sub_indices)
idx_null_userid_sub = set(sub_indices[0:NULL_USERID_SUB_COUNT])
idx_orphan_userid_sub = set(sub_indices[NULL_USERID_SUB_COUNT: NULL_USERID_SUB_COUNT + ORPHAN_USERID_SUB_COUNT])
idx_bad_date_sub = set(sub_indices[
    NULL_USERID_SUB_COUNT + ORPHAN_USERID_SUB_COUNT:
    NULL_USERID_SUB_COUNT + ORPHAN_USERID_SUB_COUNT + BAD_DATE_FORMAT_COUNT
])
idx_bad_amount_sub = set(sub_indices[
    NULL_USERID_SUB_COUNT + ORPHAN_USERID_SUB_COUNT + BAD_DATE_FORMAT_COUNT:
    NULL_USERID_SUB_COUNT + ORPHAN_USERID_SUB_COUNT + BAD_DATE_FORMAT_COUNT + BAD_AMOUNT_COUNT
])
idx_bad_status_sub = set(sub_indices[
    NULL_USERID_SUB_COUNT + ORPHAN_USERID_SUB_COUNT + BAD_DATE_FORMAT_COUNT + BAD_AMOUNT_COUNT:
    NULL_USERID_SUB_COUNT + ORPHAN_USERID_SUB_COUNT + BAD_DATE_FORMAT_COUNT + BAD_AMOUNT_COUNT + BAD_STATUS_COUNT
])


def format_payment_date(d: date, irregular: bool) -> str:
    """payment_date を文字列化する。irregular=True の場合は非標準フォーマットで揺らす"""
    if irregular:
        fmt = random.choice(["%Y/%m/%d", "%d-%m-%Y", "%m/%d/%Y", "%B %d, %Y"])
        return d.strftime(fmt)
    return d.strftime("%Y-%m-%d")  # 標準フォーマット（ISO 8601）


sub_rows = []
for i in range(1, TOTAL_SUBS + 1):
    subscription_id = f"S{str(i).zfill(4)}"

    # 契約日の一貫性を保つため、実在ユーザーのsignup_date以降で契約開始日を決める
    base_user_id = random.choice(valid_user_ids)
    signup = signup_date_lookup[base_user_id]
    start = random_date(max(signup, CONTRACT_START), CONTRACT_END_RANGE)

    end = None
    if random.random() < 0.3:  # 約3割が解約済み
        end = start + timedelta(days=random.randint(30, 365))

    plan = random.choice(PLANS)
    amount = PLAN_PRICE[plan]
    status = random.choice(VALID_PAYMENT_STATUSES)
    pay_date_raw = format_payment_date(start, irregular=(i in idx_bad_date_sub))

    # user_id への品質課題注入（日付・金額は実在ユーザー前提で生成済みのものを流用）
    user_id = base_user_id
    if i in idx_null_userid_sub:
        user_id = None  # ← 品質課題：user_idがnull
    elif i in idx_orphan_userid_sub:
        user_id = f"U9{str(i).zfill(3)}"  # ← 品質課題：user masterに存在しないuser_id

    if i in idx_bad_amount_sub:
        amount = random.choice([0.0, -round(random.uniform(100, 3000), 0)])  # ← 品質課題：0/負値

    if i in idx_bad_status_sub:
        status = random.choice(INVALID_PAYMENT_STATUSES)  # ← 品質課題：想定外のpayment_status

    sub_rows.append(Row(
        subscription_id=subscription_id,
        user_id=user_id,
        plan_type=plan,
        payment_status=status,
        amount=float(amount),
        payment_date=pay_date_raw,
        contract_start_date=start,
        contract_end_date=end,
    ))

df_subscriptions = spark.createDataFrame(sub_rows, schema=subscription_schema)

print(f"\n=== サブスクリプションデータ（{df_subscriptions.count()}件） ===")
df_subscriptions.show(10, truncate=False)


# ──────────────────────────────────────────────
# 3. ユーザーアクションイベントログ（bronze_user_events）300件
#    品質課題：
#      - user_idがnull                        6件
#      - user masterに存在しないuser_id         6件
#      - event_idの重複到着                    8件（4組の重複ペア）
#      - イベントの遅延到着（1日以上の乖離）      10件
# ──────────────────────────────────────────────

event_schema = StructType([
    StructField("event_id",            StringType(),    nullable=False),  # イベントID（本来一意想定だが重複あり）
    StructField("user_id",             StringType(),    nullable=True),   # ユーザーID（外部キー。品質課題によりnullable）
    StructField("event_type",          StringType(),    nullable=True),   # login/feature_use/upgrade_click/cancel_click/logout
    StructField("event_timestamp",     TimestampType(), nullable=True),   # イベント発生時刻
    StructField("ingestion_timestamp", TimestampType(), nullable=True),   # データ取り込み時刻（品質課題：遅延到着の検出に利用）
])

EVENT_TYPES = ["login", "feature_use", "upgrade_click", "cancel_click", "logout"]
EVENT_START = datetime(2024, 1, 1, 0, 0, 0)
EVENT_END = datetime(2024, 12, 31, 23, 59, 59)

TOTAL_EVENTS = 300
NULL_USERID_EVT_COUNT = 6
ORPHAN_USERID_EVT_COUNT = 6
DUP_EVENT_PAIRS = 4               # 4組 = 8件が重複
DELAYED_EVT_COUNT = 10

# 重複8件（4組）は「オリジナル4件＋コピー4件」を意味する。
# コピー4件を後から追加するため、通常生成は 300 - 4 = 296件
BASE_EVENT_COUNT = TOTAL_EVENTS - DUP_EVENT_PAIRS  # 296

evt_indices = list(range(1, BASE_EVENT_COUNT + 1))
random.shuffle(evt_indices)
idx_null_userid_evt = set(evt_indices[0:NULL_USERID_EVT_COUNT])
idx_orphan_userid_evt = set(evt_indices[
    NULL_USERID_EVT_COUNT: NULL_USERID_EVT_COUNT + ORPHAN_USERID_EVT_COUNT
])
idx_delayed_evt = set(evt_indices[
    NULL_USERID_EVT_COUNT + ORPHAN_USERID_EVT_COUNT:
    NULL_USERID_EVT_COUNT + ORPHAN_USERID_EVT_COUNT + DELAYED_EVT_COUNT
])

event_rows = []
for i in range(1, BASE_EVENT_COUNT + 1):
    event_id = f"E{str(i).zfill(5)}"  # E00001〜E00292

    user_id = random.choice(valid_user_ids)
    if i in idx_null_userid_evt:
        user_id = None  # ← 品質課題：user_idがnull
    elif i in idx_orphan_userid_evt:
        user_id = f"U9{str(i).zfill(3)}"  # ← 品質課題：user masterに存在しないuser_id

    ev_time = random_datetime(EVENT_START, EVENT_END)
    if i in idx_delayed_evt:
        ingest_time = ev_time + timedelta(days=random.randint(3, 7))  # ← 品質課題：遅延到着
    else:
        ingest_time = ev_time + timedelta(seconds=random.randint(1, 60))  # 通常は数十秒以内に到着

    event_rows.append(Row(
        event_id=event_id,
        user_id=user_id,
        event_type=random.choice(EVENT_TYPES),
        event_timestamp=ev_time,
        ingestion_timestamp=ingest_time,
    ))

# 重複8件（4組）：既存レコードをそのままコピーしてevent_idを重複させる
dup_source_rows = random.sample(event_rows, DUP_EVENT_PAIRS)
duplicate_rows = [Row(**r.asDict()) for r in dup_source_rows]  # ← 品質課題：event_idの重複到着

all_event_rows = event_rows + duplicate_rows
df_events = spark.createDataFrame(all_event_rows, schema=event_schema)

print(f"\n=== ユーザーアクションイベントログ（{df_events.count()}件） ===")
df_events.show(10, truncate=False)


# ──────────────────────────────────────────────
# 4. テンポラリビューとして登録（同一セッション内でSQL参照可能にする）
# ──────────────────────────────────────────────

df_users.createOrReplaceTempView("cloudbox_users")
df_subscriptions.createOrReplaceTempView("cloudbox_subscriptions")
df_events.createOrReplaceTempView("cloudbox_user_events")

print("\nテンポラリビューを登録しました: cloudbox_users / cloudbox_subscriptions / cloudbox_user_events")
print("\n=== サンプルデータ生成完了 ===")
# spark.stop() はここで呼ばない（Databricksノートブックではクラスター側がSparkSessionを管理するため）
