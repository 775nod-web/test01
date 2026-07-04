"""
小売企業向け メダリオンアーキテクチャ Bronzeレイヤー サンプルデータ生成スクリプト
============================================================================
対象データソース（Bronzeレイヤーに取り込む4テーブルのみを作成する）
  1. store_master              店舗マスター            5件
  2. product_master             商品マスター           15件
  3. customer_master             顧客/会員データ        30件
  4. pos_sales_transactions      POS売上イベント       300件
                                  （うち品質課題データ 50件を意図的に混入）

品質課題の内訳（pos_sales_transactions、各10件・合計50件）
  - 重複transaction        : 先頭10件のtransaction_idをそのまま複製
  - product_id未登録       : product_masterに存在しないproduct_idを使用
  - store_id未登録         : store_masterに存在しないstore_idを使用
  - discount null          : discount_amountをNoneのまま記録
  - 時刻形式不一致          : transaction_timeを複数の不揃いなフォーマットで記録

Gold レイヤーでの想定利用（本スクリプトはBronzeのみ。列設計はGold集計を見据えて決定）
  - 日別店舗別売上   : transaction_date + store_id + quantity/unit_price/discount_amount
  - 商品カテゴリ別売上 : product_id -> category（product_master結合） + 売上金額
  - 店舗ランキング    : store_id -> store_name/region（store_master結合） + 売上金額
  - マスター未登録レポート : store_id / product_id が各マスターに存在しないレコードの抽出
"""

from pyspark.sql import Row
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType,
    DoubleType, DateType, BooleanType, TimestampType,
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


def random_normal_time() -> str:
    """営業時間内（09:00:00〜20:59:59）のランダムな正規フォーマット時刻を返す"""
    h = random.randint(9, 20)
    m = random.randint(0, 59)
    s = random.randint(0, 59)
    return f"{h:02d}:{m:02d}:{s:02d}"


# ──────────────────────────────────────────────
# 1. 店舗マスター（store_master, 5件）
# ──────────────────────────────────────────────
#
# 表設計:
#   store_id     StringType  nullable=False  店舗ID（主キー）
#   store_name   StringType  nullable=True   店舗名
#   region       StringType  nullable=True   地方区分（店舗ランキングの地域集計に利用）
#   prefecture   StringType  nullable=True   都道府県
#   open_date    DateType    nullable=True   開店日

STORE_CATALOG = [
    ("S001", "渋谷店", "関東", "東京都", date(2015, 4, 1)),
    ("S002", "梅田店", "関西", "大阪府", date(2016, 9, 15)),
    ("S003", "栄店",   "中部", "愛知県", date(2018, 3, 20)),
    ("S004", "天神店", "九州", "福岡県", date(2019, 11, 10)),
    ("S005", "仙台店", "東北", "宮城県", date(2020, 6, 1)),
]

store_schema = StructType([
    StructField("store_id",   StringType(), nullable=False),
    StructField("store_name", StringType(), nullable=True),
    StructField("region",     StringType(), nullable=True),
    StructField("prefecture", StringType(), nullable=True),
    StructField("open_date",  DateType(),   nullable=True),
])

store_rows = [
    Row(store_id=sid, store_name=name, region=region, prefecture=pref, open_date=odate)
    for sid, name, region, pref, odate in STORE_CATALOG
]
df_stores = spark.createDataFrame(store_rows, schema=store_schema)

print("=== 店舗マスター（5件） ===")
df_stores.show(truncate=False)


# ──────────────────────────────────────────────
# 2. 商品マスター（product_master, 15件）
# ──────────────────────────────────────────────
#
# 表設計:
#   product_id    StringType  nullable=False  商品ID（主キー）
#   product_name  StringType  nullable=True   商品名
#   category      StringType  nullable=True   商品カテゴリ（商品カテゴリ別売上に利用）
#   unit_price    DoubleType  nullable=True   商品単価（円、マスター上の定価）
#   is_active     BooleanType nullable=True   販売中フラグ

PRODUCT_CATALOG = [
    ("P001", "ワイヤレスイヤホン",         "家電",   8980.0, True),
    ("P002", "モバイルバッテリー",         "家電",   3480.0, True),
    ("P003", "スマートウォッチ",           "家電",  15800.0, True),
    ("P004", "オーガニックコーヒー",       "食品",    980.0, True),
    ("P005", "グラノーラ",                 "食品",    680.0, True),
    ("P006", "プロテインバー",             "食品",    320.0, True),
    ("P007", "綿100%Tシャツ",              "衣類",   2480.0, True),
    ("P008", "デニムジーンズ",             "衣類",   6980.0, True),
    ("P009", "ウールマフラー",             "衣類",   3980.0, False),  # 販売終了商品
    ("P010", "洗剤詰め替え",               "日用品",  480.0, True),
    ("P011", "ティッシュ5箱セット",        "日用品",  680.0, True),
    ("P012", "トイレットペーパー12ロール", "日用品",  780.0, True),
    ("P013", "ミネラルウォーター500ml",    "飲料",    120.0, True),
    ("P014", "緑茶ペットボトル",           "飲料",    150.0, True),
    ("P015", "オレンジジュース1L",         "飲料",    320.0, True),
]

product_schema = StructType([
    StructField("product_id",   StringType(),  nullable=False),
    StructField("product_name", StringType(),  nullable=True),
    StructField("category",     StringType(),  nullable=True),
    StructField("unit_price",   DoubleType(),  nullable=True),
    StructField("is_active",    BooleanType(), nullable=True),
])

product_rows = [
    Row(product_id=pid, product_name=name, category=cat, unit_price=price, is_active=active)
    for pid, name, cat, price, active in PRODUCT_CATALOG
]
df_products = spark.createDataFrame(product_rows, schema=product_schema)

print("=== 商品マスター（15件） ===")
df_products.show(truncate=False)


# ──────────────────────────────────────────────
# 3. 顧客/会員データ（customer_master, 30件）
# ──────────────────────────────────────────────
#
# 表設計:
#   customer_id        StringType  nullable=False  会員ID（主キー）
#   customer_name       StringType  nullable=True   会員氏名
#   gender              StringType  nullable=True   性別（M/F）
#   birth_date          DateType    nullable=True   生年月日
#   membership_type      StringType  nullable=True   会員種別（レギュラー/シルバー/ゴールド）
#   registration_date   DateType    nullable=True   会員登録日

LAST_NAMES  = ["田中", "鈴木", "佐藤", "山田", "伊藤", "渡辺", "中村", "小林",
               "加藤", "吉田", "山口", "松本", "井上", "木村", "林", "斎藤"]
FIRST_NAMES = ["太郎", "花子", "次郎", "美咲", "健一", "由美", "翔", "あゆみ",
               "大輔", "さくら", "裕子", "誠", "和子", "拓海", "麻衣", "直樹"]
MEMBERSHIP_TYPES = ["レギュラー", "レギュラー", "レギュラー", "シルバー", "シルバー", "ゴールド"]

customer_schema = StructType([
    StructField("customer_id",        StringType(), nullable=False),
    StructField("customer_name",      StringType(), nullable=True),
    StructField("gender",             StringType(), nullable=True),
    StructField("birth_date",         DateType(),   nullable=True),
    StructField("membership_type",    StringType(), nullable=True),
    StructField("registration_date",  DateType(),   nullable=True),
])

customer_rows = []
customer_ids = []
for i in range(1, 31):
    cid = f"C{str(i).zfill(4)}"  # C0001〜C0030
    customer_ids.append(cid)
    customer_rows.append(Row(
        customer_id=cid,
        customer_name=random.choice(LAST_NAMES) + random.choice(FIRST_NAMES),
        gender=random.choice(["M", "F"]),
        birth_date=random_date(date(1955, 1, 1), date(2005, 12, 31)),
        membership_type=random.choice(MEMBERSHIP_TYPES),
        registration_date=random_date(date(2019, 1, 1), date(2026, 6, 1)),
    ))

df_customers = spark.createDataFrame(customer_rows, schema=customer_schema)

print("=== 顧客/会員データ（30件） ===")
df_customers.show(10, truncate=False)


# ──────────────────────────────────────────────
# 4. POS売上イベント（pos_sales_transactions, 300件）
#    ・正常データ 250件
#    ・重複transaction 10件           : 先頭10件のtransaction_idを複製
#    ・product_id未登録 10件          : product_masterに存在しないID
#    ・store_id未登録 10件            : store_masterに存在しないID
#    ・discount null 10件             : discount_amountがNone
#    ・時刻形式不一致 10件            : transaction_timeが複数フォーマット混在
# ──────────────────────────────────────────────
#
# 表設計:
#   transaction_id     StringType    nullable=False  取引ID（重複を含む品質課題あり）
#   transaction_date   DateType      nullable=False  取引日（日別店舗別売上に利用）
#   transaction_time   StringType    nullable=True   取引時刻（フォーマット不揃いの品質課題あり）
#   store_id           StringType    nullable=False  店舗ID（store_masterに存在しないIDを含む）
#   product_id         StringType    nullable=False  商品ID（product_masterに存在しないIDを含む）
#   customer_id        StringType    nullable=True   会員ID（非会員購入時はnull。正常な業務仕様）
#   quantity           IntegerType   nullable=False  購入数量
#   unit_price         DoubleType    nullable=False  販売単価（円）
#   discount_amount    DoubleType    nullable=True   値引き額（円、記録漏れによるnullの品質課題あり）
#   payment_method     StringType    nullable=True   支払方法
#   created_at         TimestampType nullable=False  レコード取込日時（Bronzeメタデータ）

transaction_schema = StructType([
    StructField("transaction_id",   StringType(),    nullable=False),
    StructField("transaction_date", DateType(),      nullable=False),
    StructField("transaction_time", StringType(),    nullable=True),
    StructField("store_id",         StringType(),    nullable=False),
    StructField("product_id",       StringType(),    nullable=False),
    StructField("customer_id",      StringType(),    nullable=True),
    StructField("quantity",         IntegerType(),   nullable=False),
    StructField("unit_price",       DoubleType(),    nullable=False),
    StructField("discount_amount",  DoubleType(),    nullable=True),
    StructField("payment_method",   StringType(),    nullable=True),
    StructField("created_at",       TimestampType(), nullable=False),
])

DATE_START = date(2026, 4, 6)
DATE_END   = date(2026, 7, 4)
INGESTION_TS = datetime(2026, 7, 4, 9, 0, 0)

VALID_STORE_IDS   = [s[0] for s in STORE_CATALOG]
VALID_PRODUCT_MAP = {p[0]: p[3] for p in PRODUCT_CATALOG}  # product_id -> unit_price
VALID_PRODUCT_IDS = list(VALID_PRODUCT_MAP.keys())
PAYMENT_METHODS = ["現金", "クレジットカード", "電子マネー", "QRコード決済"]


def make_normal_row(seq: int) -> Row:
    """正常なPOS売上レコードを1件生成する"""
    product_id = random.choice(VALID_PRODUCT_IDS)
    return Row(
        transaction_id=f"T{str(seq).zfill(6)}",
        transaction_date=random_date(DATE_START, DATE_END),
        transaction_time=random_normal_time(),
        store_id=random.choice(VALID_STORE_IDS),
        product_id=product_id,
        customer_id=random.choice(customer_ids) if random.random() < 0.7 else None,  # 非会員は30%
        quantity=random.randint(1, 5),
        unit_price=VALID_PRODUCT_MAP[product_id],
        discount_amount=random.choice([0.0, 0.0, 0.0, 100.0, 300.0, 500.0]),
        payment_method=random.choice(PAYMENT_METHODS),
        created_at=INGESTION_TS,
    )


# --- 正常レコード 250件（T000001〜T000250） ---
normal_rows = [make_normal_row(i) for i in range(1, 251)]

# --- 重複transaction 10件：先頭10件をそのまま複製（同一transaction_idで二重登録） ---
duplicate_rows = normal_rows[:10]

# --- product_id未登録 10件（T000251〜T000260） ---
unmatched_product_rows = []
for i in range(251, 261):
    unmatched_product_rows.append(Row(
        transaction_id=f"T{str(i).zfill(6)}",
        transaction_date=random_date(DATE_START, DATE_END),
        transaction_time=random_normal_time(),
        store_id=random.choice(VALID_STORE_IDS),
        product_id=random.choice(["P997", "P998", "P999"]),  # product_masterに存在しないID
        customer_id=random.choice(customer_ids) if random.random() < 0.7 else None,
        quantity=random.randint(1, 5),
        unit_price=round(random.uniform(300, 9000), 0),
        discount_amount=random.choice([0.0, 0.0, 100.0]),
        payment_method=random.choice(PAYMENT_METHODS),
        created_at=INGESTION_TS,
    ))

# --- store_id未登録 10件（T000261〜T000270） ---
unmatched_store_rows = []
for i in range(261, 271):
    product_id = random.choice(VALID_PRODUCT_IDS)
    unmatched_store_rows.append(Row(
        transaction_id=f"T{str(i).zfill(6)}",
        transaction_date=random_date(DATE_START, DATE_END),
        transaction_time=random_normal_time(),
        store_id=random.choice(["S997", "S998", "S999"]),  # store_masterに存在しないID
        product_id=product_id,
        customer_id=random.choice(customer_ids) if random.random() < 0.7 else None,
        quantity=random.randint(1, 5),
        unit_price=VALID_PRODUCT_MAP[product_id],
        discount_amount=random.choice([0.0, 0.0, 100.0]),
        payment_method=random.choice(PAYMENT_METHODS),
        created_at=INGESTION_TS,
    ))

# --- discount null 10件（T000271〜T000280）：discount_amountを記録漏れでNoneにする ---
null_discount_rows = []
for i in range(271, 281):
    product_id = random.choice(VALID_PRODUCT_IDS)
    null_discount_rows.append(Row(
        transaction_id=f"T{str(i).zfill(6)}",
        transaction_date=random_date(DATE_START, DATE_END),
        transaction_time=random_normal_time(),
        store_id=random.choice(VALID_STORE_IDS),
        product_id=product_id,
        customer_id=random.choice(customer_ids) if random.random() < 0.7 else None,
        quantity=random.randint(1, 5),
        unit_price=VALID_PRODUCT_MAP[product_id],
        discount_amount=None,  # 値引き記録漏れ
        payment_method=random.choice(PAYMENT_METHODS),
        created_at=INGESTION_TS,
    ))

# --- 時刻形式不一致 10件（T000281〜T000290） ---
# POS端末の機種違い等により、以下4パターンの不揃いなフォーマットが混在する想定
def malformed_time(idx: int) -> str:
    h = random.randint(9, 20)
    m = random.randint(0, 59)
    s = random.randint(0, 59)
    pattern = idx % 4
    if pattern == 0:
        return f"{h}:{m:02d}"                                   # 秒なし・0埋めなし（例: 9:5）
    elif pattern == 1:
        return f"{h:02d}{m:02d}"                                 # 区切り文字なし（例: 0905）
    elif pattern == 2:
        hour_12 = h if h <= 12 else h - 12
        meridiem = "AM" if h < 12 else "PM"
        return f"{hour_12:02d}:{m:02d}:{s:02d} {meridiem}"        # 12時間表記＋AM/PM
    else:
        return f"{h:02d}:{m:02d}:{s:02d}.{random.randint(0, 999):03d}"  # ミリ秒付き

malformed_time_rows = []
for i in range(281, 291):
    product_id = random.choice(VALID_PRODUCT_IDS)
    malformed_time_rows.append(Row(
        transaction_id=f"T{str(i).zfill(6)}",
        transaction_date=random_date(DATE_START, DATE_END),
        transaction_time=malformed_time(i),
        store_id=random.choice(VALID_STORE_IDS),
        product_id=product_id,
        customer_id=random.choice(customer_ids) if random.random() < 0.7 else None,
        quantity=random.randint(1, 5),
        unit_price=VALID_PRODUCT_MAP[product_id],
        discount_amount=random.choice([0.0, 0.0, 100.0]),
        payment_method=random.choice(PAYMENT_METHODS),
        created_at=INGESTION_TS,
    ))

# --- 全レコードを結合して DataFrame 作成（250 + 10 + 10 + 10 + 10 + 10 = 300件） ---
all_transaction_rows = (
    normal_rows
    + unmatched_product_rows
    + unmatched_store_rows
    + null_discount_rows
    + malformed_time_rows
    + duplicate_rows
)
df_transactions = spark.createDataFrame(all_transaction_rows, schema=transaction_schema)

print(f"=== POS売上イベント（合計 {df_transactions.count()} 件） ===")
df_transactions.show(20, truncate=False)


# ──────────────────────────────────────────────
# 5. データ品質サマリーの確認
# ──────────────────────────────────────────────

print("\n" + "=" * 50)
print("=== データ品質サマリー ===")
print("=" * 50)

total_count = df_transactions.count()
print(f"pos_sales_transactions 全件数: {total_count} 件")

# 重複transaction_id件数（同一transaction_idが複数回出現するレコードの超過分）
dup_groups = df_transactions.groupBy("transaction_id").count().filter(F.col("count") > 1)
dup_extra_count = dup_groups.select((F.sum("count") - F.count("count")).alias("extra")).collect()[0]["extra"] or 0
print(f"  重複transaction     : {dup_extra_count} 件（重複しているtransaction_id数: {dup_groups.count()}）")

# product_id未登録件数
invalid_product_count = df_transactions.filter(~F.col("product_id").isin(VALID_PRODUCT_IDS)).count()
print(f"  product_id未登録    : {invalid_product_count} 件")

# store_id未登録件数
invalid_store_count = df_transactions.filter(~F.col("store_id").isin(VALID_STORE_IDS)).count()
print(f"  store_id未登録      : {invalid_store_count} 件")

# discount null件数
null_discount_count = df_transactions.filter(F.col("discount_amount").isNull()).count()
print(f"  discount null       : {null_discount_count} 件")

# 時刻形式不一致件数（HH:MM:SS の24時間表記に一致しないもの）
bad_time_count = df_transactions.filter(
    ~F.col("transaction_time").rlike(r"^([01]\d|2[0-3]):[0-5]\d:[0-5]\d$")
).count()
print(f"  時刻形式不一致       : {bad_time_count} 件")

print("=" * 50)
