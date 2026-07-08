"""
デジタル銀行 不正検知PoC サンプルデータ生成スクリプト
- カスタマーマスター：20件（品質課題なし。クリーンな参照マスタ）
- アカウントマスター：25件（品質課題なし。クリーンな参照マスタ）
- トランザクションevents：126件
    - 正常：70件
    - 品質課題：
        [1] 取引ID重複                    5件（先頭5件を複製）
        [2] 顧客IDがマスターに存在しない    5件
        [3] 口座IDがマスターに存在しない    5件
        [4] 取引金額が0または負            5件
        [5] タイムスタンプ形式・TZ揺れ      8件
        [6] 国コード表記揺れ（Japan表記等） 8件
        [7] 加盟店カテゴリnull・表記揺れ    8件（null4件＋表記揺れ4件）
        [8] fraud_labelがnull              111件 / 126件（多くがnull。重複行の一部が
                                            fraud_label設定済み正常行と重なるため populated=15件）
        [9] 同一顧客の短時間複数取引        3顧客 × 4件 = 12件
- 保存先：sample スキーマ（Databricks Free Edition・Hiveメタストア）

前提：Bronze/Silver/Gold の変換処理は本スクリプトのスコープ外（別タスクで実施）
"""

from pyspark.sql import Row
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, DoubleType, DateType
)
from pyspark.sql import functions as F
import random
from datetime import date, datetime, timedelta

# Databricks ノートブックでは spark はクラスターから自動注入されるため
# SparkSession.builder は呼ばない（呼ぶと INVALID_CONNECT_URL エラーになる）

# 再現性のためのシード固定
random.seed(42)


# ──────────────────────────────────────────────
# ユーティリティ
# ──────────────────────────────────────────────

def random_date(start: date, end: date) -> date:
    """start〜end の範囲でランダムな日付を返す"""
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))


def random_datetime(start: datetime, end: datetime) -> datetime:
    """start〜end の範囲でランダムな日時を返す"""
    delta_sec = int((end - start).total_seconds())
    return start + timedelta(seconds=random.randint(0, delta_sec))


def iso_jst(dt: datetime) -> str:
    """標準形式（ISO8601, JST +09:00）の文字列に変換"""
    return dt.strftime("%Y-%m-%dT%H:%M:%S+09:00")


# ──────────────────────────────────────────────
# 1. カスタマーマスター（20件）
# ──────────────────────────────────────────────

CUSTOMER_SEGMENTS = ["個人", "法人", "個人(シニア)", "法人(中小企業)"]
RISK_CATEGORIES = ["低", "中", "高"]
RESIDENCE_COUNTRIES = ["JP", "JP", "JP", "JP", "US", "CN", "KR", "SG", "GB"]  # JPを多めに

REG_DATE_START = date(2018, 1, 1)
REG_DATE_END = date(2026, 6, 30)

customer_schema = StructType([
    StructField("customer_id",       StringType(), nullable=False),  # 顧客ID（主キー）
    StructField("customer_segment",  StringType(), nullable=True),   # 顧客属性（個人／法人など）
    StructField("risk_category",     StringType(), nullable=True),   # リスク区分（低／中／高）
    StructField("residence_country", StringType(), nullable=True),   # 居住国（ISO国コード、標準表記）
    StructField("registration_date", DateType(),   nullable=True),   # 登録日
])

customer_rows = []
for i in range(1, 21):
    customer_rows.append(Row(
        customer_id=f"CUST{str(i).zfill(3)}",
        customer_segment=random.choice(CUSTOMER_SEGMENTS),
        risk_category=random.choice(RISK_CATEGORIES),
        residence_country=random.choice(RESIDENCE_COUNTRIES),
        registration_date=random_date(REG_DATE_START, REG_DATE_END),
    ))
valid_customer_ids = [row.customer_id for row in customer_rows]

df_customers = spark.createDataFrame(customer_rows, schema=customer_schema)

print("=== カスタマーマスター（20件） ===")
df_customers.show(truncate=False)


# ──────────────────────────────────────────────
# 2. アカウントマスター（25件）
#    全顧客に1口座ずつ割当て＋5顧客は複数口座保有とする
# ──────────────────────────────────────────────

ACCOUNT_TYPES = ["普通", "当座", "定期"]
ACCOUNT_STATUSES = ["active", "active", "active", "dormant", "closed"]  # activeを多めに

account_schema = StructType([
    StructField("account_id",     StringType(), nullable=False),  # 口座ID（主キー）
    StructField("customer_id",    StringType(), nullable=True),   # 顧客ID（外部キー）
    StructField("account_type",   StringType(), nullable=True),   # 口座種別（普通／当座／定期）
    StructField("open_date",      DateType(),   nullable=True),   # 開設日
    StructField("account_status", StringType(), nullable=True),   # 口座ステータス（active/dormant/closed）
])

account_rows = []
for i, cust_id in enumerate(valid_customer_ids, start=1):
    account_rows.append(Row(
        account_id=f"ACC{str(i).zfill(4)}",
        customer_id=cust_id,
        account_type=random.choice(ACCOUNT_TYPES),
        open_date=random_date(REG_DATE_START, REG_DATE_END),
        account_status=random.choice(ACCOUNT_STATUSES),
    ))

for j, cust_id in enumerate(random.sample(valid_customer_ids, 5), start=21):
    account_rows.append(Row(
        account_id=f"ACC{str(j).zfill(4)}",
        customer_id=cust_id,
        account_type=random.choice(ACCOUNT_TYPES),
        open_date=random_date(REG_DATE_START, REG_DATE_END),
        account_status=random.choice(ACCOUNT_STATUSES),
    ))
valid_account_ids = [row.account_id for row in account_rows]

df_accounts = spark.createDataFrame(account_rows, schema=account_schema)

print("=== アカウントマスター（25件） ===")
df_accounts.show(truncate=False)


# ──────────────────────────────────────────────
# 3. トランザクションevents（126件）
# ──────────────────────────────────────────────

TRANSACTION_TYPES = ["deposit", "withdrawal", "transfer", "payment"]
MERCHANT_CATEGORIES = ["食料品", "家電", "衣料品", "飲食店", "娯楽", "公共料金", "ATM", "送金"]
OVERSEAS_COUNTRIES = ["US", "CN", "KR", "SG", "GB"]

TXN_DATE_START = datetime(2026, 6, 1, 0, 0, 0)
TXN_DATE_END = datetime(2026, 6, 30, 23, 59, 59)

transaction_schema = StructType([
    StructField("transaction_id",        StringType(),  nullable=False),  # 取引ID
    StructField("customer_id",           StringType(),  nullable=True),   # 顧客ID（外部キー）
    StructField("account_id",            StringType(),  nullable=True),   # 口座ID（外部キー）
    StructField("transaction_timestamp", StringType(),  nullable=True),   # 取引日時（文字列。形式揺れを許容）
    StructField("amount",                DoubleType(),  nullable=True),   # 取引金額（円）
    StructField("transaction_type",      StringType(),  nullable=True),   # 取引種別
    StructField("country_code",          StringType(),  nullable=True),   # 取引国コード（表記揺れを許容）
    StructField("merchant_category",     StringType(),  nullable=True),   # 加盟店カテゴリ
    StructField("fraud_label",           IntegerType(), nullable=True),   # 不正フラグ（0/1、多くがnull）
])

# --- 正常レコード 70件（うち10件にfraud_labelを設定） ---
fraud_label_indices = set(random.sample(range(70), 10))

normal_rows = []
for i in range(1, 71):
    idx = i - 1
    dt = random_datetime(TXN_DATE_START, TXN_DATE_END)
    country = "JP" if i % 5 != 0 else random.choice(OVERSEAS_COUNTRIES)  # 約20%を海外取引に
    label = (1 if idx % 4 == 0 else 0) if idx in fraud_label_indices else None
    normal_rows.append(Row(
        transaction_id=f"TXN{str(i).zfill(5)}",
        customer_id=random.choice(valid_customer_ids),
        account_id=random.choice(valid_account_ids),
        transaction_timestamp=iso_jst(dt),
        amount=round(random.uniform(1000, 500000), 0),
        transaction_type=random.choice(TRANSACTION_TYPES),
        country_code=country,
        merchant_category=random.choice(MERCHANT_CATEGORIES),
        fraud_label=label,
    ))

# --- [1] 取引ID重複 5件：先頭5件をそのまま複製 ---
duplicate_rows = normal_rows[:5]

# --- [2] 顧客IDがカスタマーマスターに存在しない 5件 ---
mismatch_customer_rows = []
for k in range(5):
    i = 71 + k
    dt = random_datetime(TXN_DATE_START, TXN_DATE_END)
    mismatch_customer_rows.append(Row(
        transaction_id=f"TXN{str(i).zfill(5)}",
        customer_id=f"CUST{str(900 + k).zfill(3)}",  # マスターに存在しない顧客ID
        account_id=random.choice(valid_account_ids),
        transaction_timestamp=iso_jst(dt),
        amount=round(random.uniform(1000, 500000), 0),
        transaction_type=random.choice(TRANSACTION_TYPES),
        country_code="JP",
        merchant_category=random.choice(MERCHANT_CATEGORIES),
        fraud_label=None,
    ))

# --- [3] 口座IDがアカウントマスターに存在しない 5件 ---
mismatch_account_rows = []
for k in range(5):
    i = 76 + k
    dt = random_datetime(TXN_DATE_START, TXN_DATE_END)
    mismatch_account_rows.append(Row(
        transaction_id=f"TXN{str(i).zfill(5)}",
        customer_id=random.choice(valid_customer_ids),
        account_id=f"ACC{str(9000 + k).zfill(4)}",  # マスターに存在しない口座ID
        transaction_timestamp=iso_jst(dt),
        amount=round(random.uniform(1000, 500000), 0),
        transaction_type=random.choice(TRANSACTION_TYPES),
        country_code="JP",
        merchant_category=random.choice(MERCHANT_CATEGORIES),
        fraud_label=None,
    ))

# --- [4] 取引金額が0または負 5件 ---
BAD_AMOUNTS = [0.0, -100.0, -5000.0, 0.0, -25000.0]
amount_issue_rows = []
for k in range(5):
    i = 81 + k
    dt = random_datetime(TXN_DATE_START, TXN_DATE_END)
    amount_issue_rows.append(Row(
        transaction_id=f"TXN{str(i).zfill(5)}",
        customer_id=random.choice(valid_customer_ids),
        account_id=random.choice(valid_account_ids),
        transaction_timestamp=iso_jst(dt),
        amount=BAD_AMOUNTS[k],
        transaction_type=random.choice(TRANSACTION_TYPES),
        country_code="JP",
        merchant_category=random.choice(MERCHANT_CATEGORIES),
        fraud_label=None,
    ))

# --- [5] タイムスタンプの形式・タイムゾーン揺れ 8件 ---
BAD_TIMESTAMPS = [
    "2026/06/15 10:23",         # スラッシュ区切り、TZなし
    "15-06-2026 10:23:45",      # 日-月-年順
    "2026-06-15T10:23:45Z",     # UTC(Zulu)表記。他はJST(+09:00)
    "20260615102345",          # 区切りなし
    "2026-06-15 10:23:45 JST",  # タイムゾーンをテキストで付与
    "",                         # 空文字
    "2026-06-15",               # 日付のみ、時刻なし
    "06/15/2026 10:23 AM",      # 米国式（月/日/年 + AM/PM）
]
timestamp_issue_rows = []
for k, ts in enumerate(BAD_TIMESTAMPS):
    i = 86 + k
    timestamp_issue_rows.append(Row(
        transaction_id=f"TXN{str(i).zfill(5)}",
        customer_id=random.choice(valid_customer_ids),
        account_id=random.choice(valid_account_ids),
        transaction_timestamp=ts,
        amount=round(random.uniform(1000, 500000), 0),
        transaction_type=random.choice(TRANSACTION_TYPES),
        country_code="JP",
        merchant_category=random.choice(MERCHANT_CATEGORIES),
        fraud_label=None,
    ))

# --- [6] 国コードの表記揺れ 8件（いずれも「日本」を意図した表記ゆれ） ---
BAD_COUNTRY_CODES = ["Japan", "JPN", "jp", "japan", "JP ", " JP", "Nippon", "JAPAN"]
country_issue_rows = []
for k, cc in enumerate(BAD_COUNTRY_CODES):
    i = 94 + k
    dt = random_datetime(TXN_DATE_START, TXN_DATE_END)
    country_issue_rows.append(Row(
        transaction_id=f"TXN{str(i).zfill(5)}",
        customer_id=random.choice(valid_customer_ids),
        account_id=random.choice(valid_account_ids),
        transaction_timestamp=iso_jst(dt),
        amount=round(random.uniform(1000, 500000), 0),
        transaction_type=random.choice(TRANSACTION_TYPES),
        country_code=cc,
        merchant_category=random.choice(MERCHANT_CATEGORIES),
        fraud_label=None,
    ))

# --- [7] 加盟店カテゴリのnull・表記揺れ 8件（null4件＋「食料品」の表記ゆれ4件） ---
BAD_MERCHANT_CATEGORIES = [None, None, None, None, "grocery", "GROCERY", "Grocery Store", "食料品 "]
merchant_issue_rows = []
for k, mc in enumerate(BAD_MERCHANT_CATEGORIES):
    i = 102 + k
    dt = random_datetime(TXN_DATE_START, TXN_DATE_END)
    merchant_issue_rows.append(Row(
        transaction_id=f"TXN{str(i).zfill(5)}",
        customer_id=random.choice(valid_customer_ids),
        account_id=random.choice(valid_account_ids),
        transaction_timestamp=iso_jst(dt),
        amount=round(random.uniform(1000, 500000), 0),
        transaction_type=random.choice(TRANSACTION_TYPES),
        country_code="JP",
        merchant_category=mc,
        fraud_label=None,
    ))

# --- [9] 同一顧客が短時間（2分間隔）に複数取引 12件（3顧客 × 4件） ---
BURST_CUSTOMERS = [valid_customer_ids[4], valid_customer_ids[9], valid_customer_ids[14]]
burst_rows = []
i = 110
for cust_id in BURST_CUSTOMERS:
    base_dt = random_datetime(TXN_DATE_START, TXN_DATE_END)
    for m in range(4):
        dt = base_dt + timedelta(minutes=m * 2)
        burst_rows.append(Row(
            transaction_id=f"TXN{str(i).zfill(5)}",
            customer_id=cust_id,
            account_id=random.choice(valid_account_ids),
            transaction_timestamp=iso_jst(dt),
            amount=round(random.uniform(50000, 300000), 0),
            transaction_type="withdrawal",
            country_code="JP",
            merchant_category="ATM",
            fraud_label=1 if m == 3 else None,  # 各バーストの最後の1件をfraud_label=1に（3件）
        ))
        i += 1

# --- 全レコードを結合して DataFrame 作成 ---
all_txn_rows = (
    normal_rows + duplicate_rows + mismatch_customer_rows + mismatch_account_rows +
    amount_issue_rows + timestamp_issue_rows + country_issue_rows +
    merchant_issue_rows + burst_rows
)
df_transactions = spark.createDataFrame(all_txn_rows, schema=transaction_schema)

print(f"=== トランザクションevents（合計 {df_transactions.count()} 件） ===")
df_transactions.show(20, truncate=False)


# ──────────────────────────────────────────────
# 4. データ品質サマリー
# ──────────────────────────────────────────────

print("\n" + "=" * 60)
print("=== データ品質サマリー ===")
print("=" * 60)

dup_ids = df_transactions.groupBy("transaction_id").count().filter(F.col("count") > 1)
print(f"[1] 取引ID重複                 : {dup_ids.count():>4} 件（重複ID数）")

invalid_customer_count = df_transactions.join(
    df_customers.select("customer_id"), on="customer_id", how="left_anti"
).count()
print(f"[2] 顧客IDがマスターに存在しない : {invalid_customer_count:>4} 件")

invalid_account_count = df_transactions.join(
    df_accounts.select("account_id"), on="account_id", how="left_anti"
).count()
print(f"[3] 口座IDがマスターに存在しない : {invalid_account_count:>4} 件")

invalid_amount_count = df_transactions.filter(F.col("amount") <= 0).count()
print(f"[4] 取引金額が0または負          : {invalid_amount_count:>4} 件")

STANDARD_TS_PATTERN = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+09:00$"
invalid_ts_count = df_transactions.filter(
    ~F.col("transaction_timestamp").rlike(STANDARD_TS_PATTERN)
).count()
print(f"[5] タイムスタンプ形式・TZ揺れ   : {invalid_ts_count:>4} 件")

VALID_COUNTRY_CODES = ["JP"] + OVERSEAS_COUNTRIES
invalid_country_count = df_transactions.filter(
    ~F.col("country_code").isin(VALID_COUNTRY_CODES)
).count()
print(f"[6] 国コード表記揺れ             : {invalid_country_count:>4} 件")

invalid_merchant_count = df_transactions.filter(
    F.col("merchant_category").isNull() | ~F.col("merchant_category").isin(MERCHANT_CATEGORIES)
).count()
print(f"[7] 加盟店カテゴリnull・表記揺れ  : {invalid_merchant_count:>4} 件")

null_fraud_label_count = df_transactions.filter(F.col("fraud_label").isNull()).count()
total_txn_count = df_transactions.count()
print(f"[8] fraud_labelがnull            : {null_fraud_label_count:>4} 件 / 全 {total_txn_count} 件")

print(f"[9] 同一顧客の短時間複数取引      : {len(BURST_CUSTOMERS):>4} 顧客 × 4件 = {len(burst_rows)} 件")
print("=" * 60)


# ──────────────────────────────────────────────
# 5. sample スキーマへの保存
#    ※ Bronze/Silver/Gold への変換処理は別タスクで実施する
# ──────────────────────────────────────────────

spark.sql("CREATE DATABASE IF NOT EXISTS sample")
spark.sql("USE sample")
print("\nデータベース 'sample' を選択しました")

(
    df_customers
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("sample.customer_master")
)
(
    df_accounts
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("sample.account_master")
)
(
    df_transactions
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("sample.transactions")
)

print("\n" + "=" * 40)
print("=== sample スキーマ 保存完了サマリー ===")
print("=" * 40)
print(f"  sample.customer_master : {spark.table('sample.customer_master').count():>6,} 件")
print(f"  sample.account_master  : {spark.table('sample.account_master').count():>6,} 件")
print(f"  sample.transactions    : {spark.table('sample.transactions').count():>6,} 件")
print("=" * 40)

# spark.stop() はここで呼ばない
# Databricks ノートブックでは SparkSession はクラスター側が管理するため、
# stop() を呼ぶと後続セルで NO_ACTIVE_SESSION エラーが発生する
