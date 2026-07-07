"""
小売メダリオンアーキテクチャ PoC - サンプルデータ生成スクリプト（Bronze層相当のデータを sample スキーマに保存）
Databricks ノートブックで実行することを前提とする

データソース（4表）
  1. POSトランザクション（pos_transactions）：310件
  2. 商品マスター（product_master）：15件
  3. 店舗マスター（store_master）：6件
  4. 会員マスター（member_master）：40件

意図的に含めたデータ品質課題（合計8種類）
  POSトランザクション（各10件、計70件）
    - product_id が商品マスターに存在しない
    - store_id が店舗マスターに存在しない
    - transaction_id の重複
    - quantity が0または負の値
    - unit_price がnullまたは負の値
    - customer_id がnull
    - transaction_timestamp の表記（フォーマット・タイムゾーン）が揺れている
  商品マスター（2件）
    - product_category がnull
"""

from pyspark.sql import Row
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, DoubleType, DateType
)
import random
from datetime import date, timedelta

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


# ──────────────────────────────────────────────
# 1. 商品マスター（15件、うち2件は品質課題としてcategoryがnull）
# ──────────────────────────────────────────────

# (product_id, product_name, category, unit_price)
# unit_price はPOS取引の単価生成時のベース価格として使用する
PRODUCT_CATALOG = [
    ("P001", "食パン",             "食品",     198.0),
    ("P002", "牛乳1L",             "食品",     218.0),
    ("P003", "国産りんご",         "食品",     328.0),
    ("P004", "洗剤詰め替え",       "日用品",   398.0),
    ("P005", "トイレットペーパー", "日用品",   498.0),
    ("P006", "歯ブラシ",           "日用品",   158.0),
    ("P007", "Tシャツ",            "衣料",     1980.0),
    ("P008", "靴下3足セット",      "衣料",     780.0),
    ("P009", "ジャケット",         "衣料",     8900.0),
    ("P010", "電池単三4本",        None,       398.0),   # 品質課題：カテゴリnull
    ("P011", "延長コード",         None,       980.0),   # 品質課題：カテゴリnull
    ("P012", "コーヒー豆200g",     "食品",     780.0),
    ("P013", "冷凍餃子",           "食品",     398.0),
    ("P014", "ハンドソープ",       "日用品",   328.0),
    ("P015", "マグカップ",         "生活雑貨", 880.0),
]

product_schema = StructType([
    StructField("product_id",   StringType(), nullable=False),  # 商品ID（主キー）
    StructField("product_name", StringType(), nullable=True),   # 商品名
    StructField("category",     StringType(), nullable=True),   # 商品カテゴリ（品質課題：nullを含む）
])

# 価格はPOS生成時に参照するため辞書化しておく（マスターテーブル自体には保持しない）
PRODUCT_BASE_PRICE = {pid: price for pid, _, _, price in PRODUCT_CATALOG}
VALID_PRODUCT_IDS = [pid for pid, _, _, _ in PRODUCT_CATALOG]

product_rows = [Row(product_id=pid, product_name=name, category=cat)
                for pid, name, cat, _ in PRODUCT_CATALOG]
df_product_master = spark.createDataFrame(product_rows, schema=product_schema)

print("=== 商品マスター（15件） ===")
df_product_master.show(truncate=False)


# ──────────────────────────────────────────────
# 2. 店舗マスター（6件、品質課題なし＝マスターは正とする）
# ──────────────────────────────────────────────

STORE_CATALOG = [
    ("S001", "新宿店", "関東"),
    ("S002", "渋谷店", "関東"),
    ("S003", "大阪店", "関西"),
    ("S004", "名古屋店", "中部"),
    ("S005", "福岡店", "九州"),
    ("S006", "札幌店", "北海道"),
]

store_schema = StructType([
    StructField("store_id",   StringType(), nullable=False),  # 店舗ID（主キー）
    StructField("store_name", StringType(), nullable=True),   # 店舗名
    StructField("region",     StringType(), nullable=True),   # 所在地域
])

VALID_STORE_IDS = [sid for sid, _, _ in STORE_CATALOG]

store_rows = [Row(store_id=sid, store_name=name, region=region)
              for sid, name, region in STORE_CATALOG]
df_store_master = spark.createDataFrame(store_rows, schema=store_schema)

print("=== 店舗マスター（6件） ===")
df_store_master.show(truncate=False)


# ──────────────────────────────────────────────
# 3. 会員マスター（40件、品質課題なし＝マスターは正とする）
# ──────────────────────────────────────────────

LAST_NAMES  = ["田中", "鈴木", "佐藤", "山田", "伊藤", "渡辺", "中村", "小林",
               "加藤", "吉田", "山口", "松本", "井上", "木村", "林", "斎藤",
               "清水", "山本", "池田", "橋本"]
FIRST_NAMES = ["太郎", "花子", "次郎", "美咲", "健一", "由美", "翔", "あゆみ",
               "大輔", "さくら", "裕子", "誠", "和子", "拓海", "麻衣", "直樹",
               "恵子", "亮", "奈々", "隆"]

member_schema = StructType([
    StructField("customer_id",        StringType(), nullable=False),  # 会員ID（主キー）
    StructField("customer_name",      StringType(), nullable=True),   # 会員氏名
    StructField("registration_date",  DateType(),   nullable=True),   # 会員登録日
])

MEMBER_START = date(2020, 1, 1)
MEMBER_END   = date(2023, 12, 31)

member_rows = [
    Row(
        customer_id=f"C{str(i).zfill(3)}",
        customer_name=random.choice(LAST_NAMES) + random.choice(FIRST_NAMES),
        registration_date=random_date(MEMBER_START, MEMBER_END),
    )
    for i in range(1, 41)
]
df_member_master = spark.createDataFrame(member_rows, schema=member_schema)

VALID_CUSTOMER_IDS = [row.customer_id for row in member_rows]

print("=== 会員マスター（40件） ===")
df_member_master.show(10, truncate=False)


# ──────────────────────────────────────────────
# 4. POSトランザクション（合計310件）
#    - 正常データ：240件
#    - 品質課題データ：7種類 × 10件 = 70件
# ──────────────────────────────────────────────

DATE_START = date(2024, 1, 1)
DATE_END   = date(2024, 6, 30)

pos_schema = StructType([
    StructField("transaction_id",        StringType(),  nullable=True),  # 取引ID（品質課題：重複を含む）
    StructField("transaction_timestamp", StringType(),  nullable=True),  # 取引日時（生データ。品質課題：フォーマット/タイムゾーン表記揺れを含むため文字列型）
    StructField("store_id",              StringType(),  nullable=True),  # 店舗ID（品質課題：マスター不一致を含む）
    StructField("product_id",            StringType(),  nullable=True),  # 商品ID（品質課題：マスター不一致を含む）
    StructField("customer_id",           StringType(),  nullable=True),  # 会員ID（品質課題：nullを含む＝非会員取引）
    StructField("quantity",              IntegerType(), nullable=True),  # 数量（品質課題：0/負値を含む）
    StructField("unit_price",            DoubleType(),  nullable=True),  # 単価・円（品質課題：null/負値を含む）
])


def make_timestamp(d: date) -> str:
    """標準フォーマット（yyyy-MM-dd HH:mm:ss）の取引日時文字列を生成する"""
    h = random.randint(9, 20)
    m = random.randint(0, 59)
    s = random.randint(0, 59)
    return f"{d.isoformat()} {h:02d}:{m:02d}:{s:02d}"


def replace_fields(row: Row, **updates) -> Row:
    """Row は namedtuple ではなく _replace を持たないため、
    dict経由でフィールドを差し替えた新しい Row を作るヘルパー"""
    d = row.asDict()
    d.update(updates)
    return Row(**d)


def make_normal_transaction(txn_id: str) -> Row:
    """正常なPOSトランザクション1件を生成する"""
    store_id = random.choice(VALID_STORE_IDS)
    product_id = random.choice(VALID_PRODUCT_IDS)
    d = random_date(DATE_START, DATE_END)
    base_price = PRODUCT_BASE_PRICE[product_id]
    return Row(
        transaction_id=txn_id,
        transaction_timestamp=make_timestamp(d),
        store_id=store_id,
        product_id=product_id,
        customer_id=random.choice(VALID_CUSTOMER_IDS),
        quantity=random.randint(1, 5),
        unit_price=base_price,
    )


# --- 正常データ 240件 ---
normal_rows = [make_normal_transaction(f"T{str(i).zfill(5)}") for i in range(1, 241)]

# --- 品質課題1：product_idが商品マスターに存在しない（10件） ---
product_mismatch_rows = []
for j in range(10):
    i = 241 + j
    row = make_normal_transaction(f"T{str(i).zfill(5)}")
    product_mismatch_rows.append(replace_fields(row, product_id=f"P{str(900 + j).zfill(3)}"))  # マスター未登録の商品ID

# --- 品質課題2：store_idが店舗マスターに存在しない（10件） ---
store_mismatch_rows = []
for j in range(10):
    i = 251 + j
    row = make_normal_transaction(f"T{str(i).zfill(5)}")
    store_mismatch_rows.append(replace_fields(row, store_id=f"S{str(900 + j).zfill(3)}"))  # マスター未登録の店舗ID

# --- 品質課題3：transaction_idの重複（正常データ先頭10件を丸ごと複製、10件追加） ---
duplicate_rows = normal_rows[:10]

# --- 品質課題4：quantityが0または負の値（10件） ---
quantity_anomaly_rows = []
for j in range(10):
    i = 261 + j
    row = make_normal_transaction(f"T{str(i).zfill(5)}")
    bad_qty = 0 if j % 2 == 0 else -random.randint(1, 3)
    quantity_anomaly_rows.append(replace_fields(row, quantity=bad_qty))

# --- 品質課題5：unit_priceがnullまたは負の値（10件） ---
price_anomaly_rows = []
for j in range(10):
    i = 271 + j
    row = make_normal_transaction(f"T{str(i).zfill(5)}")
    bad_price = None if j % 2 == 0 else -abs(row.unit_price)
    price_anomaly_rows.append(replace_fields(row, unit_price=bad_price))

# --- 品質課題6：customer_idがnull（非会員取引、10件） ---
null_customer_rows = []
for j in range(10):
    i = 281 + j
    row = make_normal_transaction(f"T{str(i).zfill(5)}")
    null_customer_rows.append(replace_fields(row, customer_id=None))

# --- 品質課題7：transaction_timestampのフォーマット/タイムゾーン表記揺れ（10件） ---
TIMESTAMP_FORMATS = [
    lambda d: d.strftime("%Y/%m/%d") + f" {random.randint(9,20):02d}:{random.randint(0,59):02d}",       # スラッシュ区切り・秒なし
    lambda d: d.strftime("%d-%m-%Y") + f"T{random.randint(9,20):02d}:{random.randint(0,59):02d}:00+09:00",  # 日-月-年 + JSTオフセット
    lambda d: d.isoformat() + f"T{random.randint(9,20):02d}:{random.randint(0,59):02d}:00Z",                 # UTC(Z)表記
    lambda d: d.strftime("%Y%m%d") + f"{random.randint(9,20):02d}{random.randint(0,59):02d}00",              # 区切り文字なし
]
timestamp_anomaly_rows = []
for j in range(10):
    i = 291 + j
    row = make_normal_transaction(f"T{str(i).zfill(5)}")
    d = random_date(DATE_START, DATE_END)
    fmt_func = TIMESTAMP_FORMATS[j % len(TIMESTAMP_FORMATS)]
    timestamp_anomaly_rows.append(replace_fields(row, transaction_timestamp=fmt_func(d)))

# --- 全レコードを結合 ---
all_pos_rows = (
    normal_rows
    + product_mismatch_rows
    + store_mismatch_rows
    + duplicate_rows
    + quantity_anomaly_rows
    + price_anomaly_rows
    + null_customer_rows
    + timestamp_anomaly_rows
)
df_pos_transactions = spark.createDataFrame(all_pos_rows, schema=pos_schema)

print(f"=== POSトランザクション（合計 {df_pos_transactions.count()} 件） ===")
df_pos_transactions.show(20, truncate=False)


# ──────────────────────────────────────────────
# 5. 一時ビューとして登録（同一セッション内でSQL参照可能にする）
# ──────────────────────────────────────────────

df_product_master.createOrReplaceTempView("product_master")
df_store_master.createOrReplaceTempView("store_master")
df_member_master.createOrReplaceTempView("member_master")
df_pos_transactions.createOrReplaceTempView("pos_transactions")

print("一時ビューを登録しました: product_master / store_master / member_master / pos_transactions")
print("\n=== サンプルデータ生成完了 ===")
# spark.stop() はここで呼ばない
# Databricks ノートブックでは SparkSession はクラスター側が管理するため、
# stop() を呼ぶと後続セルで NO_ACTIVE_SESSION エラーが発生する
