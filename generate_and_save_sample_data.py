"""
カスタマーサポート チケット分析 PoC - サンプルデータ生成・保存スクリプト
（Databricks Free Edition Notebook 用）

前回設計したテーブル定義に基づき、Bronze相当のサンプルデータを生成し、
`sample` スキーマに Delta テーブルとして保存する。

保存先: sample.customer_master / sample.contract_data / sample.support_tickets

- 顧客マスター（customer_master）        : 15件（クリーン）
- 契約データ（contract_data）            : 15件（クリーン）
- サポートチケット（support_tickets）    : 53件
    - クリーンなレコード: 26件
    - 品質課題を含むレコード: 27件
      （顧客マスター不一致2 / 顧客ID欠損2 / チケットID重複2 /
        優先度表記揺れ4 / ステータス表記揺れ4 / カテゴリ欠損3 /
        センチメント欠損3 / 解決時間欠損2 / 解決時間異常値2 /
        作成日時フォーマット揺れ3）

データソースはKnowledge base記載の3つ（カスタマーマスター / サポートチケッツ /
コントラクトデータ）のみを対象とし、Product usage summaryは対象外とする。
"""

from pyspark.sql import Row
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType, DateType
)
import random
from datetime import date, datetime, timedelta

# Databricks ノートブックでは spark はクラスターから自動注入されるため
# SparkSession.builder は呼ばない（呼ぶと INVALID_CONNECT_URL エラーになる）

# 再現性のためのシード固定
random.seed(42)


# ──────────────────────────────────────────────
# 0. 保存先スキーマの作成（無ければ作成）
# ──────────────────────────────────────────────

spark.sql("CREATE SCHEMA IF NOT EXISTS sample")
spark.sql("USE sample")
print("スキーマ 'sample' を選択しました（存在しない場合は作成済み）")


# ──────────────────────────────────────────────
# ユーティリティ
# ──────────────────────────────────────────────

def random_date(start: date, end: date) -> date:
    """start〜end の範囲でランダムな日付を返す"""
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))


def random_datetime_str(start: date, end: date) -> str:
    """start〜end の範囲でランダムな日時を正規フォーマット文字列で返す
    正規フォーマット: 'YYYY-MM-DD HH:MM:SS'
    """
    d = random_date(start, end)
    dt = datetime(d.year, d.month, d.day,
                   random.randint(0, 23), random.randint(0, 59), random.randint(0, 59))
    return dt.strftime("%Y-%m-%d %H:%M:%S")


# ──────────────────────────────────────────────
# 1. 顧客マスター（customer_master） 15件
#    データソース: カスタマーマスター（顧客ID、企業名、プラン、ARR、CSMオーナー、地域）
# ──────────────────────────────────────────────

# customer_id, company_name, plan, arr, csm_owner, region
CUSTOMER_MASTER = [
    ("C001", "株式会社サンライズマート",     "Premium",    12_000_000.0, "佐藤", "関東"),
    ("C002", "グリーンフィールド商事",       "Standard",    4_800_000.0, "田中", "関西"),
    ("C003", "北海道フレッシュフーズ",       "Enterprise", 25_000_000.0, "佐藤", "北海道"),
    ("C004", "中部リテールパートナーズ",     "Standard",    5_200_000.0, "鈴木", "中部"),
    ("C005", "九州マーケットプレイス",       "Premium",     9_600_000.0, "田中", "九州"),
    ("C006", "東北ストアチェーン",           "Free",                0.0, "鈴木", "東北"),
    ("C007", "関西デパートメント",           "Enterprise", 30_000_000.0, "佐藤", "関西"),
    ("C008", "四国ショッピングモール",       "Standard",    4_500_000.0, "鈴木", "四国"),
    ("C009", "中国リージョンストア",         "Premium",     8_800_000.0, "田中", "中国"),
    ("C010", "沖縄トロピカルマート",         "Free",                0.0, "鈴木", "沖縄"),
    ("C011", "首都圏スーパーマーケット",     "Enterprise", 28_000_000.0, "佐藤", "関東"),
    ("C012", "近畿フードリテール",           "Standard",    5_000_000.0, "田中", "関西"),
    ("C013", "東海コンビニエンス",           "Premium",    10_500_000.0, "鈴木", "中部"),
    ("C014", "北陸ホームセンター",           "Standard",    4_700_000.0, "佐藤", "中部"),
    ("C015", "山陰リテールグループ",         "Free",                0.0, "田中", "中国"),
]

customer_master_schema = StructType([
    StructField("customer_id",   StringType(), nullable=False),  # 顧客ID（主キー）
    StructField("company_name",  StringType(), nullable=True),   # 会社名
    StructField("plan",          StringType(), nullable=True),   # 契約プラン（Free/Standard/Premium/Enterprise）
    StructField("arr",           DoubleType(), nullable=True),   # 年間契約金額 ARR（円）
    StructField("csm_owner",     StringType(), nullable=True),   # 担当CSM（Customer Success Manager）名
    StructField("region",        StringType(), nullable=True),   # 顧客の所在地域
])

df_customer_master = spark.createDataFrame(
    [Row(customer_id=cid, company_name=name, plan=plan, arr=arr, csm_owner=csm, region=region)
     for cid, name, plan, arr, csm, region in CUSTOMER_MASTER],
    schema=customer_master_schema,
)

(
    df_customer_master
    .write.format("delta").mode("overwrite").option("overwriteSchema", "true")
    .saveAsTable("sample.customer_master")
)
print(f"sample.customer_master 保存完了: {spark.table('sample.customer_master').count()} 件")


# ──────────────────────────────────────────────
# 2. 契約データ（contract_data） 15件
#    データソース: コントラクトデータ（顧客ID、契約開始日、更新日、契約ステータス、ARR）
# ──────────────────────────────────────────────

# customer_id, contract_start_date, renewal_date(Noneあり=解約により更新なし), contract_status, arr
CONTRACT_DATA = [
    ("C001", date(2024, 4, 1),  date(2026, 4, 1),  "Active",          12_000_000.0),
    ("C002", date(2023, 10, 1), date(2025, 10, 1), "Active",           4_800_000.0),
    ("C003", date(2022, 1, 15), date(2026, 1, 15), "Active",          25_000_000.0),
    ("C004", date(2024, 7, 1),  date(2025, 7, 1),  "Pending Renewal",  5_200_000.0),
    ("C005", date(2023, 5, 1),  date(2025, 5, 1),  "Active",           9_600_000.0),
    ("C006", date(2025, 1, 10), date(2026, 1, 10), "Active",                 0.0),
    ("C007", date(2021, 9, 1),  date(2026, 9, 1),  "Active",          30_000_000.0),
    ("C008", date(2024, 2, 1),  None,               "Cancelled",        4_500_000.0),
    ("C009", date(2023, 11, 1), date(2025, 11, 1), "Active",           8_800_000.0),
    ("C010", date(2025, 3, 1),  date(2026, 3, 1),  "Active",                 0.0),
    ("C011", date(2022, 6, 1),  date(2026, 6, 1),  "Active",          28_000_000.0),
    ("C012", date(2024, 8, 1),  date(2025, 8, 1),  "Active",           5_000_000.0),
    ("C013", date(2023, 12, 1), date(2025, 12, 1), "Active",          10_500_000.0),
    ("C014", date(2024, 5, 1),  None,               "Cancelled",        4_700_000.0),
    ("C015", date(2025, 2, 1),  date(2026, 2, 1),  "Active",                 0.0),
]

contract_data_schema = StructType([
    StructField("customer_id",         StringType(), nullable=False),  # 顧客ID（外部キー: customer_master）
    StructField("contract_start_date", DateType(),   nullable=True),   # 契約開始日
    StructField("renewal_date",        DateType(),   nullable=True),   # 契約更新日（解約済みの場合は無し）
    StructField("contract_status",     StringType(), nullable=True),   # 契約ステータス（Active/Cancelled/Pending Renewal）
    StructField("arr",                 DoubleType(), nullable=True),   # 契約時点のARR（円）
])

df_contract_data = spark.createDataFrame(
    [Row(customer_id=cid, contract_start_date=start, renewal_date=renewal,
         contract_status=status, arr=arr)
     for cid, start, renewal, status, arr in CONTRACT_DATA],
    schema=contract_data_schema,
)

(
    df_contract_data
    .write.format("delta").mode("overwrite").option("overwriteSchema", "true")
    .saveAsTable("sample.contract_data")
)
print(f"sample.contract_data 保存完了: {spark.table('sample.contract_data').count()} 件")


# ──────────────────────────────────────────────
# 3. サポートチケット（support_tickets）
#    データソース: サポートチケッツ（チケットID、顧客ID、作成日時、優先度、
#                  ステータス、カテゴリ、センチメント、解決時間）
#
#    Bronze相当の生データを想定し、あえて型・制約を緩く設計する
#    （created_at は STRING、priority/status も STRING で正規値以外を許容）。
# ──────────────────────────────────────────────

VALID_CUSTOMER_IDS = [row[0] for row in CUSTOMER_MASTER]

CATEGORIES = ["Billing", "Technical Issue", "Feature Request", "Account Management", "Onboarding"]
SENTIMENTS = ["Positive", "Neutral", "Negative"]
PRIORITIES_CANONICAL = ["Low", "Medium", "High"]
STATUSES_CANONICAL = ["Open", "In Progress", "Resolved", "Closed"]
RESOLVED_STATUSES = {"Resolved", "Closed"}

DATE_START = date(2026, 6, 1)
DATE_END = date(2026, 6, 14)

support_tickets_schema = StructType([
    StructField("ticket_id",         StringType(), nullable=False),  # チケットID（本来は一意だが、Bronzeでは一意性を保証しない＝重複が発生し得る）
    StructField("customer_id",       StringType(), nullable=True),   # 顧客ID（外部キー。ソース起因でnullや顧客マスター不一致が発生し得る）
    StructField("created_at",        StringType(), nullable=False),  # チケット作成日時（生データ。フォーマット揺れがあるためSTRING型で保持）
    StructField("priority",          StringType(), nullable=True),   # 優先度（生データ。大文字小文字/表記揺れあり）
    StructField("status",            StringType(), nullable=True),   # ステータス（生データ。大文字小文字/表記揺れあり）
    StructField("category",          StringType(), nullable=True),   # 問い合わせカテゴリ（欠損あり）
    StructField("sentiment",         StringType(), nullable=True),   # 顧客の感情（Positive/Neutral/Negative。欠損あり）
    StructField("resolution_hours",  DoubleType(), nullable=True),   # 解決までの時間（時間単位）。未解決なら本来null、解決済なのにnull/異常値のケースが品質課題
    StructField("subject",           StringType(), nullable=True),   # チケット件名（参考情報）
])


def make_subject(category: str, ticket_id: str) -> str:
    return f"{category}に関する問い合わせ（{ticket_id}）"


# --- クリーンなレコード 26件 ---
clean_rows = []
for i in range(1, 27):
    ticket_id = f"T{i:04d}"
    customer_id = random.choice(VALID_CUSTOMER_IDS)
    created_at = random_datetime_str(DATE_START, DATE_END)
    priority = random.choice(PRIORITIES_CANONICAL)
    status = random.choice(STATUSES_CANONICAL)
    category = random.choice(CATEGORIES)
    sentiment = random.choice(SENTIMENTS)
    resolution_hours = round(random.uniform(1, 72), 1) if status in RESOLVED_STATUSES else None

    clean_rows.append(Row(
        ticket_id=ticket_id, customer_id=customer_id, created_at=created_at,
        priority=priority, status=status, category=category, sentiment=sentiment,
        resolution_hours=resolution_hours, subject=make_subject(category, ticket_id),
    ))

# --- 品質課題1: 顧客マスター不一致 2件（存在しないcustomer_id） ---
unmatched_customer_rows = []
for j, cid in enumerate(["C098", "C099"]):
    ticket_id = f"T{27 + j:04d}"
    unmatched_customer_rows.append(Row(
        ticket_id=ticket_id, customer_id=cid,
        created_at=random_datetime_str(DATE_START, DATE_END),
        priority=random.choice(PRIORITIES_CANONICAL), status="Open",
        category=random.choice(CATEGORIES), sentiment=random.choice(SENTIMENTS),
        resolution_hours=None, subject=make_subject("Technical Issue", ticket_id),
    ))

# --- 品質課題2: 顧客ID欠損 2件 ---
null_customer_rows = []
for k in range(2):
    ticket_id = f"T{29 + k:04d}"
    null_customer_rows.append(Row(
        ticket_id=ticket_id, customer_id=None,
        created_at=random_datetime_str(DATE_START, DATE_END),
        priority=random.choice(PRIORITIES_CANONICAL), status="Open",
        category=random.choice(CATEGORIES), sentiment=random.choice(SENTIMENTS),
        resolution_hours=None, subject=make_subject("Billing", ticket_id),
    ))

# --- 品質課題3: チケットID重複 2件（既存レコードをそのままコピー = 再取り込みを想定） ---
duplicate_rows = [clean_rows[4], clean_rows[11]]  # T0005, T0012 を重複させる

# --- 品質課題4: 優先度の表記揺れ 4件（"High"が正規値だが表記が揺れている） ---
priority_variant_rows = []
for m, variant in enumerate(["high", "HIGH", "urget", "urgent"]):
    ticket_id = f"T{31 + m:04d}"
    status = random.choice(STATUSES_CANONICAL)
    priority_variant_rows.append(Row(
        ticket_id=ticket_id, customer_id=random.choice(VALID_CUSTOMER_IDS),
        created_at=random_datetime_str(DATE_START, DATE_END),
        priority=variant, status=status,
        category=random.choice(CATEGORIES), sentiment=random.choice(SENTIMENTS),
        resolution_hours=round(random.uniform(1, 72), 1) if status in RESOLVED_STATUSES else None,
        subject=make_subject("Technical Issue", ticket_id),
    ))

# --- 品質課題5: ステータスの表記揺れ 4件 ---
status_variant_rows = []
for n, variant in enumerate(["open", "inprogress", "resolved", "close"]):
    ticket_id = f"T{35 + n:04d}"
    is_resolved_like = variant in ("resolved", "close")
    status_variant_rows.append(Row(
        ticket_id=ticket_id, customer_id=random.choice(VALID_CUSTOMER_IDS),
        created_at=random_datetime_str(DATE_START, DATE_END),
        priority=random.choice(PRIORITIES_CANONICAL), status=variant,
        category=random.choice(CATEGORIES), sentiment=random.choice(SENTIMENTS),
        resolution_hours=round(random.uniform(1, 72), 1) if is_resolved_like else None,
        subject=make_subject("Feature Request", ticket_id),
    ))

# --- 品質課題6: カテゴリ欠損 3件 ---
category_null_rows = []
for p in range(3):
    ticket_id = f"T{39 + p:04d}"
    status = random.choice(STATUSES_CANONICAL)
    category_null_rows.append(Row(
        ticket_id=ticket_id, customer_id=random.choice(VALID_CUSTOMER_IDS),
        created_at=random_datetime_str(DATE_START, DATE_END),
        priority=random.choice(PRIORITIES_CANONICAL), status=status,
        category=None, sentiment=random.choice(SENTIMENTS),
        resolution_hours=round(random.uniform(1, 72), 1) if status in RESOLVED_STATUSES else None,
        subject=f"問い合わせ（{ticket_id}）",
    ))

# --- 品質課題7: センチメント欠損 3件 ---
sentiment_null_rows = []
for q in range(3):
    ticket_id = f"T{42 + q:04d}"
    status = random.choice(STATUSES_CANONICAL)
    sentiment_null_rows.append(Row(
        ticket_id=ticket_id, customer_id=random.choice(VALID_CUSTOMER_IDS),
        created_at=random_datetime_str(DATE_START, DATE_END),
        priority=random.choice(PRIORITIES_CANONICAL), status=status,
        category=random.choice(CATEGORIES), sentiment=None,
        resolution_hours=round(random.uniform(1, 72), 1) if status in RESOLVED_STATUSES else None,
        subject=make_subject("Account Management", ticket_id),
    ))

# --- 品質課題8: 解決時間欠損（Resolved/Closedなのにnull） 2件 ---
resolution_null_rows = []
for r in range(2):
    ticket_id = f"T{45 + r:04d}"
    resolution_null_rows.append(Row(
        ticket_id=ticket_id, customer_id=random.choice(VALID_CUSTOMER_IDS),
        created_at=random_datetime_str(DATE_START, DATE_END),
        priority=random.choice(PRIORITIES_CANONICAL), status="Resolved",
        category=random.choice(CATEGORIES), sentiment=random.choice(SENTIMENTS),
        resolution_hours=None,  # 解決済みなのに欠損（異常）
        subject=make_subject("Technical Issue", ticket_id),
    ))

# --- 品質課題9: 解決時間の異常値（極端に大きい） 2件 ---
resolution_outlier_rows = []
for s, hours in enumerate([9999.0, 15000.5]):
    ticket_id = f"T{47 + s:04d}"
    resolution_outlier_rows.append(Row(
        ticket_id=ticket_id, customer_id=random.choice(VALID_CUSTOMER_IDS),
        created_at=random_datetime_str(DATE_START, DATE_END),
        priority=random.choice(PRIORITIES_CANONICAL), status="Closed",
        category=random.choice(CATEGORIES), sentiment=random.choice(SENTIMENTS),
        resolution_hours=hours,  # 720時間(30日)を大きく超える異常値
        subject=make_subject("Billing", ticket_id),
    ))

# --- 品質課題10: 作成日時のフォーマット揺れ 3件 ---
created_at_variant_rows = []
variant_datetimes = [
    "2026/06/07 09:30",          # 区切り文字が "/"
    "07-06-2026 14:00:00",       # DD-MM-YYYY 順序違い
    "2026-06-10T11:00:00Z",      # ISO8601 (T区切り + Z)
]
for t, dt_str in enumerate(variant_datetimes):
    ticket_id = f"T{49 + t:04d}"
    status = random.choice(STATUSES_CANONICAL)
    created_at_variant_rows.append(Row(
        ticket_id=ticket_id, customer_id=random.choice(VALID_CUSTOMER_IDS),
        created_at=dt_str,
        priority=random.choice(PRIORITIES_CANONICAL), status=status,
        category=random.choice(CATEGORIES), sentiment=random.choice(SENTIMENTS),
        resolution_hours=round(random.uniform(1, 72), 1) if status in RESOLVED_STATUSES else None,
        subject=make_subject("Onboarding", ticket_id),
    ))

# --- 全レコードを結合して DataFrame 作成・保存 ---
all_ticket_rows = (
    clean_rows
    + unmatched_customer_rows
    + null_customer_rows
    + duplicate_rows
    + priority_variant_rows
    + status_variant_rows
    + category_null_rows
    + sentiment_null_rows
    + resolution_null_rows
    + resolution_outlier_rows
    + created_at_variant_rows
)
df_support_tickets = spark.createDataFrame(all_ticket_rows, schema=support_tickets_schema)

(
    df_support_tickets
    .write.format("delta").mode("overwrite").option("overwriteSchema", "true")
    .saveAsTable("sample.support_tickets")
)
print(f"sample.support_tickets 保存完了: {spark.table('sample.support_tickets').count()} 件")

print("\n=== sample スキーマへの保存が完了しました ===")
print("  sample.customer_master")
print("  sample.contract_data")
print("  sample.support_tickets")
# spark.stop() はここで呼ばない
# Databricks ノートブックでは SparkSession はクラスター側が管理するため、
# stop() を呼ぶと後続セルで NO_ACTIVE_SESSION エラーが発生する
