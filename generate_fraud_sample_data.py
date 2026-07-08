"""
不正検知データプラットフォーム サンプルデータ生成スクリプト
- 顧客マスタ    (bronze_customers)  : 8件
- 口座マスタ    (bronze_accounts)   : 9件
- 取引イベント  (bronze_transactions): 37件（意図的な品質課題を含む）

保存先スキーマ: sample（存在しない場合は自動作成）
  - sample.bronze_customers
  - sample.bronze_accounts
  - sample.bronze_transactions

動作確認環境: Databricks Free Edition
"""

from pyspark.sql import Row
from pyspark.sql.types import (
    StructType, StructField, StringType, DecimalType, DateType, TimestampType
)
from datetime import date, datetime
from decimal import Decimal

# Databricks ノートブックでは spark はクラスターから自動注入されるため
# SparkSession.builder は呼ばない（呼ぶと INVALID_CONNECT_URL エラーになる）


# ──────────────────────────────────────────────
# 0. 保存先スキーマの作成
# ──────────────────────────────────────────────

spark.sql("CREATE SCHEMA IF NOT EXISTS sample")
spark.sql("USE sample")
print("スキーマ 'sample' を選択しました")


def d(v):
    """Decimal型への変換ヘルパー"""
    return Decimal(str(v))


# 全テーブル共通のロード時刻（技術列）
INGEST_TS = datetime(2026, 7, 8, 9, 0, 0)


# ──────────────────────────────────────────────
# 1. 顧客マスタ（bronze_customers）8件
#    品質課題は含めない（マスタは整備済みという前提）
# ──────────────────────────────────────────────

customers_schema = StructType([
    StructField("customer_id",        StringType(),    nullable=False),  # 顧客ID（主キー）
    StructField("customer_type",      StringType(),    nullable=True),   # 顧客区分（individual/corporate）
    StructField("birth_date",         DateType(),      nullable=True),   # 生年月日（法人はNULL）
    StructField("risk_category",      StringType(),    nullable=True),   # リスク区分（low/medium/high）
    StructField("residence_country",  StringType(),    nullable=True),   # 居住国コード（ISO2）
    StructField("registration_date",  DateType(),       nullable=False), # 顧客登録日
    StructField("ingest_timestamp",   TimestampType(), nullable=False),  # ロード時刻（技術列）
])

customers_data = [
    ("CUST001", "individual", date(1985, 5, 12), "low",    "JP", date(2019, 4, 1),  INGEST_TS),
    ("CUST002", "individual", date(1990, 8, 23), "medium", "JP", date(2020, 6, 15), INGEST_TS),
    ("CUST003", "individual", date(1978, 12, 1), "high",   "JP", date(2021, 1, 10), INGEST_TS),
    ("CUST004", "individual", date(1995, 2, 17), "low",    "US", date(2018, 9, 23), INGEST_TS),
    ("CUST005", "corporate",  None,              "medium", "JP", date(2022, 3, 5),  INGEST_TS),
    ("CUST006", "individual", date(1982, 7, 4),  "low",    "GB", date(2017, 11, 30), INGEST_TS),
    ("CUST007", "individual", date(2001, 3, 30), "medium", "JP", date(2023, 7, 19), INGEST_TS),
    ("CUST008", "individual", date(1975, 10, 9), "low",    "CN", date(2020, 12, 1), INGEST_TS),
]

df_customers = spark.createDataFrame(
    [Row(*row) for row in customers_data], schema=customers_schema
)

print(f"=== 顧客マスタ（{df_customers.count()}件） ===")
df_customers.show(truncate=False)


# ──────────────────────────────────────────────
# 2. 口座マスタ（bronze_accounts）9件
#    品質課題は含めない（CUST002のみ複数口座保有）
# ──────────────────────────────────────────────

accounts_schema = StructType([
    StructField("account_id",       StringType(),    nullable=False),  # 口座ID（主キー）
    StructField("customer_id",      StringType(),    nullable=False),  # 顧客ID（外部キー）
    StructField("account_type",     StringType(),    nullable=True),   # 口座種別
    StructField("open_date",        DateType(),      nullable=False),  # 口座開設日
    StructField("account_status",   StringType(),    nullable=True),   # 口座ステータス
    StructField("ingest_timestamp", TimestampType(), nullable=False),  # ロード時刻（技術列）
])

accounts_data = [
    ("ACC001", "CUST001", "savings",  date(2019, 4, 1),   "active",    INGEST_TS),
    ("ACC002", "CUST002", "savings",  date(2020, 6, 15),  "active",    INGEST_TS),
    ("ACC003", "CUST003", "checking", date(2021, 1, 10),  "active",    INGEST_TS),
    ("ACC004", "CUST004", "savings",  date(2018, 9, 23),  "active",    INGEST_TS),
    ("ACC005", "CUST005", "checking", date(2022, 3, 5),   "active",    INGEST_TS),
    ("ACC006", "CUST006", "savings",  date(2017, 11, 30), "dormant",   INGEST_TS),
    ("ACC007", "CUST007", "savings",  date(2023, 7, 19),  "active",    INGEST_TS),
    ("ACC008", "CUST008", "checking", date(2020, 12, 1),  "suspended", INGEST_TS),
    ("ACC009", "CUST002", "credit",   date(2023, 1, 5),   "active",    INGEST_TS),
]

df_accounts = spark.createDataFrame(
    [Row(*row) for row in accounts_data], schema=accounts_schema
)

print(f"=== 口座マスタ（{df_accounts.count()}件） ===")
df_accounts.show(truncate=False)


# ──────────────────────────────────────────────
# 3. 取引イベント（bronze_transactions）37件
#    Knowledge baseの品質課題9種類を意図的に含める
# ──────────────────────────────────────────────

transactions_schema = StructType([
    StructField("transaction_id",     StringType(),     nullable=False),  # 取引ID（重複あり）
    StructField("customer_id",        StringType(),     nullable=False),  # 顧客ID（マスタ不一致あり）
    StructField("account_id",         StringType(),     nullable=False),  # 口座ID（マスタ不一致あり）
    StructField("transaction_ts",     StringType(),     nullable=False),  # 取引日時（生文字列、形式揺れあり）
    StructField("amount",             DecimalType(18, 2), nullable=False),# 取引金額（異常値あり）
    StructField("transaction_type",   StringType(),     nullable=True),   # 取引種別
    StructField("country_code",       StringType(),     nullable=True),   # 国コード（表記揺れあり）
    StructField("merchant_category",  StringType(),     nullable=True),   # 加盟店カテゴリ（NULL・表記揺れあり）
    StructField("fraud_label",        StringType(),     nullable=True),   # 不正ラベル（NULL多数）
    StructField("ingest_timestamp",   TimestampType(),  nullable=False),  # ロード時刻（技術列）
])

transactions_data = [
    # --- クリーンな基本データ (12件) ---
    ("TX1001", "CUST001", "ACC001", "2026-07-01T09:15:00+09:00", d(3200),   "purchase",        "JP", "Grocery",       None,    INGEST_TS),
    ("TX1002", "CUST001", "ACC001", "2026-07-02T14:20:00+09:00", d(15000),  "purchase",        "JP", "Electronics",   "legit", INGEST_TS),
    ("TX1003", "CUST002", "ACC002", "2026-07-01T11:00:00+09:00", d(5000),   "transfer",        "JP", "Utilities",     None,    INGEST_TS),
    ("TX1004", "CUST002", "ACC009", "2026-07-03T08:45:00+09:00", d(2200),   "purchase",        "JP", "Restaurant",    None,    INGEST_TS),
    ("TX1005", "CUST004", "ACC004", "2026-07-01T22:10:00+09:00", d(48000),  "purchase",        "US", "Travel",        None,    INGEST_TS),
    ("TX1006", "CUST005", "ACC005", "2026-07-02T10:30:00+09:00", d(120000), "transfer",        "JP", "Utilities",     "legit", INGEST_TS),
    ("TX1007", "CUST006", "ACC006", "2026-07-04T16:00:00+09:00", d(7600),   "purchase",        "GB", "Entertainment", None,    INGEST_TS),
    ("TX1008", "CUST007", "ACC007", "2026-07-05T13:25:00+09:00", d(990),    "purchase",        "JP", "Grocery",       None,    INGEST_TS),
    ("TX1009", "CUST008", "ACC008", "2026-07-01T19:40:00+09:00", d(30000),  "withdrawal",      "CN", None,            None,    INGEST_TS),  # ATM出金=正当なNULL
    ("TX1010", "CUST003", "ACC003", "2026-07-02T12:00:00+09:00", d(4300),   "purchase",        "JP", "Grocery",       "fraud", INGEST_TS),
    ("TX1011", "CUST001", "ACC001", "2026-07-06T09:00:00+09:00", d(1800),   "atm",             "JP", None,            None,    INGEST_TS),  # ATM出金=正当なNULL
    ("TX1012", "CUST002", "ACC002", "2026-07-06T17:30:00+09:00", d(9200),   "purchase",        "JP", "Restaurant",    None,    INGEST_TS),

    # --- 同一顧客の短時間複数取引（バーストパターン, CUST003, 4件, 約9分間） ---
    ("TX1013", "CUST003", "ACC003", "2026-07-03T23:05:00+09:00", d(9800),   "online_transfer", "JP", "Electronics",   None,    INGEST_TS),
    ("TX1014", "CUST003", "ACC003", "2026-07-03T23:09:00+09:00", d(9800),   "online_transfer", "JP", "Electronics",   None,    INGEST_TS),
    ("TX1015", "CUST003", "ACC003", "2026-07-03T23:12:00+09:00", d(15000),  "online_transfer", "JP", "Electronics",   "fraud", INGEST_TS),
    ("TX1016", "CUST003", "ACC003", "2026-07-03T23:14:00+09:00", d(22000),  "online_transfer", "JP", "Electronics",   "fraud", INGEST_TS),

    # --- transaction_id 重複（TX1005, TX1012 を再取込, 2件） ---
    ("TX1005", "CUST004", "ACC004", "2026-07-01T22:10:00+09:00", d(48000),  "purchase",        "US", "Travel",        None,    INGEST_TS),
    ("TX1012", "CUST002", "ACC002", "2026-07-06T17:30:00+09:00", d(9200),   "purchase",        "JP", "Restaurant",    None,    INGEST_TS),

    # --- customer_id が顧客マスタに不一致 (2件) ---
    ("TX1017", "CUST099", "ACC005", "2026-07-04T10:00:00+09:00", d(6000),   "purchase",        "JP", "Grocery",       None,    INGEST_TS),
    ("TX1018", "CUST098", "ACC007", "2026-07-05T15:20:00+09:00", d(12500),  "transfer",        "JP", "Utilities",     None,    INGEST_TS),

    # --- account_id が口座マスタに不一致 (2件) ---
    ("TX1019", "CUST001", "ACC099", "2026-07-02T08:10:00+09:00", d(3300),   "purchase",        "JP", "Grocery",       None,    INGEST_TS),
    ("TX1020", "CUST006", "ACC098", "2026-07-04T19:45:00+09:00", d(8800),   "purchase",        "GB", "Entertainment", None,    INGEST_TS),

    # --- 金額異常：0円・マイナス (2件) ---
    ("TX1021", "CUST007", "ACC007", "2026-07-03T11:15:00+09:00", d(0),      "purchase",        "JP", "Grocery",       "fraud", INGEST_TS),
    ("TX1022", "CUST008", "ACC008", "2026-07-05T09:30:00+09:00", d(-1500),  "purchase",        "CN", "Electronics",   "fraud", INGEST_TS),

    # --- タイムスタンプ形式・タイムゾーン揺れ (4件) ---
    ("TX1023", "CUST001", "ACC001", "2026-07-02 21:00:00",       d(2500),   "purchase",        "JP", "Restaurant",    None,    INGEST_TS),
    ("TX1024", "CUST002", "ACC002", "2026/07/03 07:45:00",       d(1700),   "purchase",        "JP", "Grocery",       None,    INGEST_TS),
    ("TX1025", "CUST004", "ACC004", "07-04-2026 13:10:00",       d(9400),   "purchase",        "US", "Travel",        None,    INGEST_TS),
    ("TX1026", "CUST005", "ACC005", "1751603400",                d(26000),  "transfer",        "JP", "Utilities",     None,    INGEST_TS),

    # --- カントリーコード表記揺れ（すべて日本） (4件) ---
    ("TX1027", "CUST001", "ACC001", "2026-07-05T10:00:00+09:00", d(4100),   "purchase",        "Japan", "Grocery",     None,    INGEST_TS),
    ("TX1028", "CUST002", "ACC002", "2026-07-05T11:00:00+09:00", d(6200),   "purchase",        "JPN",   "Restaurant",  None,    INGEST_TS),
    ("TX1029", "CUST007", "ACC007", "2026-07-06T12:00:00+09:00", d(3300),   "purchase",        "jp",    "Grocery",     None,    INGEST_TS),
    ("TX1030", "CUST008", "ACC008", "2026-07-06T13:00:00+09:00", d(5100),   "purchase",        " JP ",  "Electronics", None,    INGEST_TS),

    # --- 加盟店カテゴリ NULL・表記揺れ (5件) ---
    ("TX1031", "CUST003", "ACC003", "2026-07-05T14:00:00+09:00", d(7200),   "purchase",        "JP", None,            None,    INGEST_TS),
    ("TX1032", "CUST004", "ACC004", "2026-07-06T15:00:00+09:00", d(8300),   "purchase",        "US", None,            None,    INGEST_TS),
    ("TX1033", "CUST005", "ACC005", "2026-07-06T16:00:00+09:00", d(15400),  "purchase",        "JP", "grocery",       None,    INGEST_TS),
    ("TX1034", "CUST006", "ACC006", "2026-07-07T09:00:00+09:00", d(6700),   "purchase",        "GB", "RESTAURANT",    "legit", INGEST_TS),
    ("TX1035", "CUST001", "ACC001", "2026-07-07T10:00:00+09:00", d(9100),   "purchase",        "JP", "Electronic",    None,    INGEST_TS),
]

df_transactions = spark.createDataFrame(
    [Row(*row) for row in transactions_data], schema=transactions_schema
)

print(f"=== 取引イベント（{df_transactions.count()}件） ===")
df_transactions.show(40, truncate=False)


# ──────────────────────────────────────────────
# 4. Delta テーブルとして sample スキーマへ保存
# ──────────────────────────────────────────────

(
    df_customers
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("sample.bronze_customers")
)

(
    df_accounts
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("sample.bronze_accounts")
)

(
    df_transactions
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("sample.bronze_transactions")
)

print("\n" + "=" * 50)
print("=== Delta テーブル保存完了 ===")
print("=" * 50)
print(f"  sample.bronze_customers    : {spark.table('sample.bronze_customers').count():>4,} 件")
print(f"  sample.bronze_accounts     : {spark.table('sample.bronze_accounts').count():>4,} 件")
print(f"  sample.bronze_transactions : {spark.table('sample.bronze_transactions').count():>4,} 件")
print("=" * 50)

# spark.stop() はここで呼ばない
# Databricks ノートブックでは SparkSession はクラスター側が管理するため、
# stop() を呼ぶと後続セルで NO_ACTIVE_SESSION エラーが発生する
