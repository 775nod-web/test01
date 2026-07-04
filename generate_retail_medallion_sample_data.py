"""
小売メダリオンアーキテクチャ サンプルデータ生成スクリプト（Databricks Free Edition想定）
==================================================================

■ ビジネス目的
    店舗・商品別の売上を可視化し、売上低下や人気商品の傾向を早期に把握する

■ 対象データソース（今回作成する4表）
    1. store_master     … 店舗マスター
    2. product_master   … 商品マスター
    3. customer_master  … 顧客/会員データ
    4. pos_sales        … POS売上イベント（トランザクション）

■ Gold層アウトプット（想定）
    - 日別店舗別売上         … pos_sales × store_master（日付・店舗軸で集計）
    - 商品カテゴリ別売上     … pos_sales × product_master（カテゴリ軸で集計）
    - 店舗ランキング         … pos_sales × store_master（売上合計で店舗を順位付け）
    - マスター未登録レポート … pos_sales の store_id / product_id が
                              マスターに存在しないレコードを抽出

■ 意図的に含めるデータ品質課題（pos_sales のみ）
    1. 重複 transaction        … 同一 transaction_id が複数出現
    2. product_id 未登録       … product_master に存在しない product_id
    3. store_id 未登録         … store_master に存在しない store_id
    4. discount null           … discount_amount が NULL
    5. 時刻形式不一致          … transaction_datetime のフォーマットが不統一

Databricks ノートブックでは spark はクラスターから自動注入されるため
SparkSession.builder は呼ばない（呼ぶと INVALID_CONNECT_URL エラーになる）。
"""

from pyspark.sql import Row
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, DoubleType, DateType
)
from pyspark.sql import functions as F
import random
from datetime import date, timedelta

# 再現性のためのシード固定
random.seed(42)


# ──────────────────────────────────────────────
# ユーティリティ
# ──────────────────────────────────────────────

def random_date(start: date, end: date) -> date:
    """start〜end の範囲でランダムな日付を返す"""
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))


def random_datetime_str(start: date, end: date) -> str:
    """start〜end の範囲でランダムな日時文字列（標準フォーマット）を返す"""
    d = random_date(start, end)
    h = random.randint(8, 21)   # 営業時間帯（8時〜21時）
    m = random.randint(0, 59)
    s = random.randint(0, 59)
    return f"{d.isoformat()} {h:02d}:{m:02d}:{s:02d}"


DATE_START = date(2024, 1, 1)
DATE_END = date(2024, 12, 31)


# ================================================================
# Output 1: サンプルデータ 表設計一覧（列名・データ型・nullable・説明）
# ================================================================

table_design = [
    ("store_master",    "store_id",             "StringType",  "NOT NULL", "店舗ID（主キー）"),
    ("store_master",    "store_name",           "StringType",  "NULL",     "店舗名"),
    ("store_master",    "region",               "StringType",  "NULL",     "地域（店舗ランキング等の分析軸）"),
    ("store_master",    "store_type",           "StringType",  "NULL",     "店舗タイプ（都市型／郊外型／ロードサイド）"),

    ("product_master",  "product_id",           "StringType",  "NOT NULL", "商品ID（主キー）"),
    ("product_master",  "product_name",         "StringType",  "NULL",     "商品名"),
    ("product_master",  "category",             "StringType",  "NULL",     "商品カテゴリ（商品カテゴリ別売上の集計軸）"),
    ("product_master",  "unit_price",           "DoubleType",  "NULL",     "標準単価（円）"),

    ("customer_master", "customer_id",          "StringType",  "NOT NULL", "顧客ID（主キー）"),
    ("customer_master", "customer_name",        "StringType",  "NULL",     "顧客名"),
    ("customer_master", "membership_type",      "StringType",  "NULL",     "会員種別（一般会員／プレミアム会員／ゲスト）"),
    ("customer_master", "registration_date",    "DateType",    "NULL",     "会員登録日"),

    ("pos_sales", "transaction_id",       "StringType", "NOT NULL", "取引ID。品質課題「重複transaction」により同一値が複数出現する場合あり"),
    ("pos_sales", "store_id",             "StringType", "NULL",     "店舗ID（外部キー）。品質課題「store_id未登録」によりマスター未存在の値を含む"),
    ("pos_sales", "product_id",           "StringType", "NULL",     "商品ID（外部キー）。品質課題「product_id未登録」によりマスター未存在の値を含む"),
    ("pos_sales", "customer_id",          "StringType", "NULL",     "顧客ID（外部キー）。非会員（ゲスト）購入時はnullを許容"),
    ("pos_sales", "transaction_datetime", "StringType", "NULL",     "取引日時。POSレジからの生データを想定しString型で保持。品質課題「時刻形式不一致」により複数フォーマットが混在"),
    ("pos_sales", "quantity",             "IntegerType", "NULL",    "購入数量"),
    ("pos_sales", "unit_price",           "DoubleType", "NULL",     "単価（円）"),
    ("pos_sales", "discount_amount",      "DoubleType", "NULL",     "割引額（円）。品質課題「discount null」によりnullを含む（値0は「値引きなし」を表す正常値であり区別する）"),
    ("pos_sales", "sales_amount",         "DoubleType", "NULL",     "売上金額（円）＝ quantity × unit_price － discount_amount"),
]

design_schema = StructType([
    StructField("table_name",   StringType()),
    StructField("column_name",  StringType()),
    StructField("data_type",    StringType()),
    StructField("nullable",     StringType()),
    StructField("description",  StringType()),
])
df_table_design = spark.createDataFrame(table_design, schema=design_schema)

print("=" * 80)
print("Output 1: サンプルデータ 表設計一覧")
print("=" * 80)
df_table_design.show(100, truncate=False)


# ================================================================
# Output 2: データ件数・品質課題件数の設計
# ================================================================

data_volume_design = [
    ("store_master",    5,   0,  "品質課題なし（クリーンなマスターデータ）"),
    ("product_master",  15,  0,  "品質課題なし（クリーンなマスターデータ）"),
    ("customer_master", 30,  0,  "品質課題なし（クリーンなマスターデータ）"),
    ("pos_sales", 235, 35,
     "重複transaction:5件 / product_id未登録:5件 / store_id未登録:5件 / "
     "discount null:10件 / 時刻形式不一致:10件"),
]

volume_schema = StructType([
    StructField("table_name",         StringType()),
    StructField("total_count",        IntegerType()),
    StructField("quality_issue_count", IntegerType()),
    StructField("quality_issue_description", StringType()),
])
df_volume_design = spark.createDataFrame(data_volume_design, schema=volume_schema)

print("=" * 80)
print("Output 2: データ件数・品質課題件数の設計")
print("=" * 80)
df_volume_design.show(20, truncate=False)


# ================================================================
# Output 3: サンプルデータ生成コード
# ================================================================

# ──────────────────────────────────────────────
# 1. 店舗マスター（5件・クリーン）
# ──────────────────────────────────────────────

STORE_CATALOG = [
    ("S001", "渋谷店",             "関東",   "都市型"),
    ("S002", "梅田店",             "近畿",   "都市型"),
    ("S003", "名古屋駅前店",       "中部",   "都市型"),
    ("S004", "札幌郊外店",         "北海道", "郊外型"),
    ("S005", "福岡ロードサイド店", "九州",   "ロードサイド"),
]

store_schema = StructType([
    StructField("store_id",   StringType(), nullable=False),
    StructField("store_name", StringType(), nullable=True),
    StructField("region",     StringType(), nullable=True),
    StructField("store_type", StringType(), nullable=True),
])

store_rows = [Row(store_id=sid, store_name=name, region=region, store_type=stype)
              for sid, name, region, stype in STORE_CATALOG]
df_stores = spark.createDataFrame(store_rows, schema=store_schema)

print("=== 店舗マスター（5件） ===")
df_stores.show(truncate=False)


# ──────────────────────────────────────────────
# 2. 商品マスター（15件・クリーン）
# ──────────────────────────────────────────────

PRODUCT_CATALOG = [
    ("P001", "おにぎり(鮭)",           "食品",   150.0),
    ("P002", "サンドイッチ",           "食品",   320.0),
    ("P003", "ペットボトル茶500ml",    "食品",   150.0),
    ("P004", "カップ麺",               "食品",   200.0),
    ("P005", "冷凍餃子",               "食品",   398.0),
    ("P006", "洗濯用洗剤",             "日用品", 298.0),
    ("P007", "ティッシュペーパー",     "日用品", 250.0),
    ("P008", "歯ブラシ",               "日用品", 120.0),
    ("P009", "シャンプー",             "日用品", 680.0),
    ("P010", "靴下",                   "衣料",   500.0),
    ("P011", "Tシャツ",                 "衣料",   1500.0),
    ("P012", "ハンカチ",               "衣料",   600.0),
    ("P013", "モバイルバッテリー",     "家電",   2980.0),
    ("P014", "ワイヤレスイヤホン",     "家電",   3980.0),
    ("P015", "乾電池(単3形4本)",       "家電",   480.0),
]

product_schema = StructType([
    StructField("product_id",   StringType(), nullable=False),
    StructField("product_name", StringType(), nullable=True),
    StructField("category",     StringType(), nullable=True),
    StructField("unit_price",   DoubleType(), nullable=True),
])

product_rows = [Row(product_id=pid, product_name=name, category=cat, unit_price=price)
                 for pid, name, cat, price in PRODUCT_CATALOG]
df_products = spark.createDataFrame(product_rows, schema=product_schema)

print("=== 商品マスター（15件） ===")
df_products.show(truncate=False)


# ──────────────────────────────────────────────
# 3. 顧客/会員データ（30件・クリーン）
# ──────────────────────────────────────────────

LAST_NAMES = ["田中", "鈴木", "佐藤", "山田", "伊藤", "渡辺", "中村", "小林",
              "加藤", "吉田", "山口", "松本", "井上", "木村", "林"]
FIRST_NAMES = ["太郎", "花子", "次郎", "美咲", "健一", "由美", "翔", "あゆみ",
               "大輔", "さくら", "裕子", "誠", "和子", "拓海", "麻衣"]
MEMBERSHIP_TYPES = ["一般会員", "プレミアム会員", "ゲスト"]

customer_schema = StructType([
    StructField("customer_id",       StringType(), nullable=False),
    StructField("customer_name",     StringType(), nullable=True),
    StructField("membership_type",  StringType(), nullable=True),
    StructField("registration_date", DateType(),   nullable=True),
])

customer_rows = [
    Row(
        customer_id=f"C{str(i).zfill(3)}",
        customer_name=random.choice(LAST_NAMES) + random.choice(FIRST_NAMES),
        membership_type=random.choice(MEMBERSHIP_TYPES),
        registration_date=random_date(date(2020, 1, 1), date(2024, 12, 31)),
    )
    for i in range(1, 31)
]
df_customers = spark.createDataFrame(customer_rows, schema=customer_schema)

print("=== 顧客/会員データ（30件） ===")
df_customers.show(10, truncate=False)


# ──────────────────────────────────────────────
# 4. POS売上イベント（235件 = 正常200件 + 品質課題35件）
# ──────────────────────────────────────────────

VALID_STORE_IDS = [sid for sid, *_ in STORE_CATALOG]
VALID_PRODUCT_IDS = {pid: price for pid, _, _, price in PRODUCT_CATALOG}
VALID_CUSTOMER_IDS = [f"C{str(i).zfill(3)}" for i in range(1, 31)]


def make_normal_row(txn_id: str) -> Row:
    """マスターと整合する正常なPOS取引レコードを1件生成する"""
    store_id = random.choice(VALID_STORE_IDS)
    product_id = random.choice(list(VALID_PRODUCT_IDS.keys()))
    unit_price = VALID_PRODUCT_IDS[product_id]
    quantity = random.randint(1, 5)
    # 20%はゲスト購入（顧客IDなし）
    customer_id = None if random.random() < 0.2 else random.choice(VALID_CUSTOMER_IDS)
    discount_amount = random.choice([0.0, 0.0, 0.0, 50.0, 100.0, 200.0])  # 大半は値引きなし
    sales_amount = round(quantity * unit_price - discount_amount, 0)

    return Row(
        transaction_id=txn_id,
        store_id=store_id,
        product_id=product_id,
        customer_id=customer_id,
        transaction_datetime=random_datetime_str(DATE_START, DATE_END),
        quantity=quantity,
        unit_price=unit_price,
        discount_amount=discount_amount,
        sales_amount=sales_amount,
    )


pos_schema = StructType([
    StructField("transaction_id",       StringType(),  nullable=False),
    StructField("store_id",             StringType(),  nullable=True),
    StructField("product_id",           StringType(),  nullable=True),
    StructField("customer_id",          StringType(),  nullable=True),
    StructField("transaction_datetime", StringType(),  nullable=True),
    StructField("quantity",             IntegerType(), nullable=True),
    StructField("unit_price",           DoubleType(),  nullable=True),
    StructField("discount_amount",      DoubleType(),  nullable=True),
    StructField("sales_amount",         DoubleType(),  nullable=True),
])

# --- 正常レコード 200件 ---
normal_rows = [make_normal_row(f"T{str(i).zfill(6)}") for i in range(1, 201)]

# --- 品質課題1: 重複transaction 5件（先頭5件をそのまま複製） ---
duplicate_rows = normal_rows[:5]

# --- 品質課題2: product_id未登録 5件 ---
unregistered_product_rows = []
for k in range(5):
    txn_id = f"T{str(200 + k + 1).zfill(6)}"
    unregistered_product_rows.append(Row(
        transaction_id=txn_id,
        store_id=random.choice(VALID_STORE_IDS),
        product_id=f"P9{90 + k}",           # 商品マスターに存在しないID
        customer_id=random.choice(VALID_CUSTOMER_IDS),
        transaction_datetime=random_datetime_str(DATE_START, DATE_END),
        quantity=random.randint(1, 5),
        unit_price=random.choice(list(VALID_PRODUCT_IDS.values())),
        discount_amount=0.0,
        sales_amount=round(random.uniform(150, 3000), 0),
    ))

# --- 品質課題3: store_id未登録 5件 ---
unregistered_store_rows = []
for k in range(5):
    txn_id = f"T{str(205 + k + 1).zfill(6)}"
    product_id = random.choice(list(VALID_PRODUCT_IDS.keys()))
    unregistered_store_rows.append(Row(
        transaction_id=txn_id,
        store_id=f"S9{90 + k}",             # 店舗マスターに存在しないID
        product_id=product_id,
        customer_id=random.choice(VALID_CUSTOMER_IDS),
        transaction_datetime=random_datetime_str(DATE_START, DATE_END),
        quantity=random.randint(1, 5),
        unit_price=VALID_PRODUCT_IDS[product_id],
        discount_amount=0.0,
        sales_amount=round(random.uniform(150, 3000), 0),
    ))

# --- 品質課題4: discount null 10件 ---
discount_null_rows = []
for k in range(10):
    txn_id = f"T{str(210 + k + 1).zfill(6)}"
    product_id = random.choice(list(VALID_PRODUCT_IDS.keys()))
    quantity = random.randint(1, 5)
    unit_price = VALID_PRODUCT_IDS[product_id]
    discount_null_rows.append(Row(
        transaction_id=txn_id,
        store_id=random.choice(VALID_STORE_IDS),
        product_id=product_id,
        customer_id=random.choice(VALID_CUSTOMER_IDS),
        transaction_datetime=random_datetime_str(DATE_START, DATE_END),
        quantity=quantity,
        unit_price=unit_price,
        discount_amount=None,               # 割引額が欠損（0との区別が必要な品質課題）
        sales_amount=round(quantity * unit_price, 0),
    ))

# --- 品質課題5: 時刻形式不一致 10件 ---
BAD_DATETIME_FORMATS = [
    "2024/05/01 13:45",
    "01-05-2024 13:45:00",
    "20240501134500",
    "2024-05-01T13:45:00Z",
    "May 1, 2024 01:45 PM",
    "2024.05.01 13:45",
    "1/5/2024 13:45",
    "2024-05-01 13時45分",
    "20240501",
    "2024-05-01 13:45:00 JST",
]
time_format_rows = []
for k in range(10):
    txn_id = f"T{str(220 + k + 1).zfill(6)}"
    product_id = random.choice(list(VALID_PRODUCT_IDS.keys()))
    quantity = random.randint(1, 5)
    unit_price = VALID_PRODUCT_IDS[product_id]
    time_format_rows.append(Row(
        transaction_id=txn_id,
        store_id=random.choice(VALID_STORE_IDS),
        product_id=product_id,
        customer_id=random.choice(VALID_CUSTOMER_IDS),
        transaction_datetime=BAD_DATETIME_FORMATS[k],  # 標準フォーマットと異なる形式
        quantity=quantity,
        unit_price=unit_price,
        discount_amount=0.0,
        sales_amount=round(quantity * unit_price, 0),
    ))

all_pos_rows = (
    normal_rows
    + duplicate_rows
    + unregistered_product_rows
    + unregistered_store_rows
    + discount_null_rows
    + time_format_rows
)
df_pos_sales = spark.createDataFrame(all_pos_rows, schema=pos_schema)

print(f"=== POS売上イベント（合計 {df_pos_sales.count()} 件） ===")
df_pos_sales.show(20, truncate=False)


# ================================================================
# Output 4（前半）: 生成直後のデータ品質チェック
# ================================================================

print("=" * 80)
print("生成データの品質チェック（保存前の確認）")
print("=" * 80)

dup_txn = df_pos_sales.groupBy("transaction_id").count().filter(F.col("count") > 1)
print(f"重複 transaction_id: {dup_txn.count()} グループ "
      f"({dup_txn.agg(F.sum('count')).first()[0]} 件)")

unregistered_product_count = df_pos_sales.filter(
    ~F.col("product_id").isin(list(VALID_PRODUCT_IDS.keys()))
).count()
print(f"product_id 未登録: {unregistered_product_count} 件")

unregistered_store_count = df_pos_sales.filter(
    ~F.col("store_id").isin(VALID_STORE_IDS)
).count()
print(f"store_id 未登録: {unregistered_store_count} 件")

discount_null_count = df_pos_sales.filter(F.col("discount_amount").isNull()).count()
print(f"discount_amount null: {discount_null_count} 件")

# 標準フォーマット "yyyy-MM-dd HH:mm:ss" に一致しないレコードを不一致とみなす
STANDARD_DATETIME_PATTERN = r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$"
time_mismatch_count = df_pos_sales.filter(
    ~F.col("transaction_datetime").rlike(STANDARD_DATETIME_PATTERN)
).count()
print(f"時刻形式不一致: {time_mismatch_count} 件")


# ──────────────────────────────────────────────
# 5. テンポラリビューとして登録（同一セッション内でSQL参照可能にする）
# ──────────────────────────────────────────────

df_stores.createOrReplaceTempView("store_master")
df_products.createOrReplaceTempView("product_master")
df_customers.createOrReplaceTempView("customer_master")
df_pos_sales.createOrReplaceTempView("pos_sales")

print("テンポラリビューを登録しました: store_master / product_master / customer_master / pos_sales")
print("\n=== 全データ生成完了 ===")
# spark.stop() はここで呼ばない（Databricksノートブックではクラスター側がセッション管理するため）
