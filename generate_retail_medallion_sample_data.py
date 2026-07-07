"""
小売メダリオンアーキテクチャ Bronzeレイヤー サンプルデータ生成スクリプト
（Databricks Free Edition Notebook 実行想定）

# データソース（4表・データソースに指定されたもののみ作成）
1. POSトランザクション（pos_transactions）：200件
   - 商品マスター不整合  8件
   - 店舗マスター不整合  8件
   - 取引IDの重複       8件（既存8件を複製した追加行）
   - 数量異常（0/負値）  8件
   - 単価異常（null/負値）8件
   - タイムスタンプ表記揺れ 8件
   - 会員ID欠損（非会員取引） 12件
   - 上記に該当しない正常データ 140件
2. 商品マスター（product_master）：20件（うちカテゴリnull 2件）
3. 店舗マスター（store_master）：5件
4. 会員マスター（member_master）：30件

Gold層で必要となる「日次×店舗×カテゴリ」の集計に対応できるよう、
7日間 × 5店舗 × 4カテゴリ（20商品）× 30会員の組み合わせでデータを生成する。
"""

from pyspark.sql import Row
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, DoubleType, DateType
)
import random
import datetime as _dt
from datetime import date, timedelta

# Databricks ノートブックでは spark はクラスターから自動注入されるため
# SparkSession.builder は呼ばない（呼ぶと INVALID_CONNECT_URL エラーになる）

# 再現性のためのシード固定
random.seed(42)


# ──────────────────────────────────────────────
# 1. 店舗マスター（store_master）：5件
# ──────────────────────────────────────────────

STORE_CATALOG = [
    ("S001", "東京本店",     "東京都", "直営店"),
    ("S002", "大阪梅田店",   "大阪府", "直営店"),
    ("S003", "名古屋栄店",   "愛知県", "FC店"),
    ("S004", "札幌すすきの店", "北海道", "FC店"),
    ("S005", "福岡天神店",   "福岡県", "直営店"),
]

# 店舗マスターのスキーマ定義
# | 列名        | 型          | nullable | 説明                         |
# |-------------|-------------|----------|------------------------------|
# | store_id    | StringType  | False    | 店舗ID（主キー）             |
# | store_name  | StringType  | True     | 店舗名                       |
# | prefecture  | StringType  | True     | 都道府県                     |
# | store_type  | StringType  | True     | 店舗形態（直営店 / FC店）    |
store_schema = StructType([
    StructField("store_id",   StringType(), nullable=False),
    StructField("store_name", StringType(), nullable=True),
    StructField("prefecture", StringType(), nullable=True),
    StructField("store_type", StringType(), nullable=True),
])

store_rows = [Row(store_id=sid, store_name=name, prefecture=pref, store_type=stype)
              for sid, name, pref, stype in STORE_CATALOG]
df_stores = spark.createDataFrame(store_rows, schema=store_schema)

print("=== 店舗マスター（5件） ===")
df_stores.show(truncate=False)


# ──────────────────────────────────────────────
# 2. 商品マスター（product_master）：20件
#    ・4カテゴリ × 5商品
#    ・品質課題：カテゴリnull 2件（新商品でカテゴリ未設定を想定）
# ──────────────────────────────────────────────

PRODUCT_CATALOG = [
    ("P001", "食パン",           "食品",   250.0),
    ("P002", "牛乳1L",           "食品",   198.0),
    ("P003", "冷凍餃子",         "食品",   398.0),
    ("P004", "カップ麺",         "食品",   168.0),
    ("P005", "お茶2L",           "食品",   158.0),
    ("P006", "トイレットペーパー", "日用品", 398.0),
    ("P007", "食器用洗剤",       "日用品", 258.0),
    ("P008", "歯ブラシ",         "日用品", 128.0),
    ("P009", "ティッシュ5箱",     "日用品", 348.0),
    ("P010", "洗濯洗剤",         "日用品", 498.0),
    ("P011", "Tシャツ",          "衣料品", 1980.0),
    ("P012", "靴下3足セット",     "衣料品", 780.0),
    ("P013", "デニムパンツ",     "衣料品", 4980.0),
    ("P014", "パーカー",         "衣料品", 3980.0),
    ("P015", "ネックウォーマー", "衣料品", 1280.0),
    ("P016", "LED電球",          "家電",   680.0),
    ("P017", "モバイルバッテリー", "家電",  2980.0),
    ("P018", "電池単三8本",       "家電",  498.0),
    ("P019", "新商品サンプルA",  None,     None),   # 品質課題：カテゴリ未設定
    ("P020", "新商品サンプルB",  None,     980.0),  # 品質課題：カテゴリ未設定
]

# 商品マスターのスキーマ定義
# | 列名             | 型          | nullable | 説明                                             |
# |------------------|-------------|----------|--------------------------------------------------|
# | product_id       | StringType  | False    | 商品ID（主キー）                                 |
# | product_name     | StringType  | True     | 商品名                                           |
# | product_category | StringType  | True     | 商品カテゴリ（品質課題：null 2件を含む）         |
# | standard_price   | DoubleType  | True     | 標準単価（円）                                   |
product_schema = StructType([
    StructField("product_id",       StringType(), nullable=False),
    StructField("product_name",     StringType(), nullable=True),
    StructField("product_category", StringType(), nullable=True),
    StructField("standard_price",   DoubleType(),  nullable=True),
])

product_rows = [Row(product_id=pid, product_name=name, product_category=cat, standard_price=price)
                for pid, name, cat, price in PRODUCT_CATALOG]
df_products = spark.createDataFrame(product_rows, schema=product_schema)

print("=== 商品マスター（20件） ===")
df_products.show(truncate=False)


# ──────────────────────────────────────────────
# 3. 会員マスター（member_master）：30件
# ──────────────────────────────────────────────

LAST_NAMES  = ["田中", "鈴木", "佐藤", "山田", "伊藤", "渡辺", "中村", "小林",
               "加藤", "吉田", "山口", "松本", "井上", "木村", "林", "斎藤",
               "清水", "山本", "池田", "橋本"]
FIRST_NAMES = ["太郎", "花子", "次郎", "美咲", "健一", "由美", "翔", "あゆみ",
               "大輔", "さくら", "裕子", "誠", "和子", "拓海", "麻衣", "直樹",
               "恵子", "亮", "奈々", "隆"]

# 会員マスターのスキーマ定義
# | 列名               | 型          | nullable | 説明                       |
# |--------------------|-------------|----------|----------------------------|
# | customer_id        | StringType  | False    | 会員ID（主キー）           |
# | customer_name      | StringType  | True     | 会員名                     |
# | gender             | StringType  | True     | 性別                       |
# | birth_year         | IntegerType | True     | 生年                       |
# | registration_date  | DateType    | True     | 会員登録日                 |
member_schema = StructType([
    StructField("customer_id",       StringType(),  nullable=False),
    StructField("customer_name",     StringType(),  nullable=True),
    StructField("gender",            StringType(),  nullable=True),
    StructField("birth_year",        IntegerType(), nullable=True),
    StructField("registration_date", DateType(),    nullable=True),
])


def random_date(start: date, end: date) -> date:
    """start〜end の範囲でランダムな日付を返す"""
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))


REG_START = date(2020, 1, 1)
REG_END   = date(2023, 12, 31)

member_rows = [
    Row(
        customer_id=f"M{str(i).zfill(3)}",
        customer_name=random.choice(LAST_NAMES) + random.choice(FIRST_NAMES),
        gender=random.choice(["男性", "女性"]),
        birth_year=random.randint(1950, 2005),
        registration_date=random_date(REG_START, REG_END),
    )
    for i in range(1, 31)
]
df_members = spark.createDataFrame(member_rows, schema=member_schema)

print("=== 会員マスター（30件） ===")
df_members.show(10, truncate=False)


# ──────────────────────────────────────────────
# 4. POSトランザクション（pos_transactions）：200件
#    Bronzeレイヤーは生データをそのまま保持する方針のため、
#    transaction_timestamp はあえて StringType とし、
#    表記揺れ（フォーマット/タイムゾーン混在）を許容する。
# ──────────────────────────────────────────────

# POSトランザクションのスキーマ定義
# | 列名                   | 型          | nullable | 説明                                                           |
# |------------------------|-------------|----------|-----------------------------------------------------------------|
# | transaction_id         | StringType  | False    | 取引明細ID（品質課題：重複を含む）                              |
# | transaction_timestamp  | StringType  | True     | 取引日時（生データ文字列。品質課題：フォーマット/timezone揺れ） |
# | store_id               | StringType  | True     | 店舗ID（外部キー。品質課題：店舗マスター不整合）                |
# | product_id             | StringType  | True     | 商品ID（外部キー。品質課題：商品マスター不整合）                |
# | customer_id            | StringType  | True     | 会員ID（非会員取引はnull。品質課題としても計測）                |
# | quantity               | IntegerType | True     | 販売数量（品質課題：0または負値）                               |
# | unit_price             | DoubleType  | True     | 単価・円（品質課題：nullまたは負値）                            |
pos_schema = StructType([
    StructField("transaction_id",        StringType(),  nullable=False),
    StructField("transaction_timestamp", StringType(),  nullable=True),
    StructField("store_id",              StringType(),  nullable=True),
    StructField("product_id",            StringType(),  nullable=True),
    StructField("customer_id",           StringType(),  nullable=True),
    StructField("quantity",              IntegerType(), nullable=True),
    StructField("unit_price",            DoubleType(),  nullable=True),
])

TXN_DATE_START = date(2024, 1, 1)
TXN_DATE_END   = date(2024, 1, 7)   # 7日間

VALID_STORE_IDS   = [sid for sid, *_ in STORE_CATALOG]
VALID_PRODUCT_IDS = [pid for pid, *_ in PRODUCT_CATALOG]
VALID_CUSTOMER_IDS = [f"M{str(i).zfill(3)}" for i in range(1, 31)]
PRODUCT_PRICE = {pid: price for pid, _, _, price in PRODUCT_CATALOG if price is not None}


def random_timestamp(d: date) -> str:
    """ISO形式（正常フォーマット）のタイムスタンプ文字列を返す"""
    h = random.randint(9, 20)
    m = random.randint(0, 59)
    s = random.randint(0, 59)
    return f"{d.isoformat()} {h:02d}:{m:02d}:{s:02d}"


# --- 正常データ 140件 ---
normal_rows = []
for i in range(1, 141):
    txn_date = random_date(TXN_DATE_START, TXN_DATE_END)
    product_id = random.choice(VALID_PRODUCT_IDS[:18])  # カテゴリありの商品から選択
    normal_rows.append(Row(
        transaction_id=f"T{str(i).zfill(5)}",
        transaction_timestamp=random_timestamp(txn_date),
        store_id=random.choice(VALID_STORE_IDS),
        product_id=product_id,
        customer_id=random.choice(VALID_CUSTOMER_IDS),
        quantity=random.randint(1, 5),
        unit_price=PRODUCT_PRICE.get(product_id, 500.0) * random.uniform(0.95, 1.05),
    ))

# --- 商品マスター不整合 8件（商品マスターに存在しないproduct_id） ---
product_mismatch_rows = []
for j in range(8):
    i = 141 + j
    txn_date = random_date(TXN_DATE_START, TXN_DATE_END)
    product_mismatch_rows.append(Row(
        transaction_id=f"T{str(i).zfill(5)}",
        transaction_timestamp=random_timestamp(txn_date),
        store_id=random.choice(VALID_STORE_IDS),
        product_id=f"P{str(900 + j).zfill(3)}",  # マスター未登録の商品ID
        customer_id=random.choice(VALID_CUSTOMER_IDS),
        quantity=random.randint(1, 5),
        unit_price=round(random.uniform(100, 3000), 0),
    ))

# --- 店舗マスター不整合 8件（店舗マスターに存在しないstore_id） ---
store_mismatch_rows = []
for j in range(8):
    i = 149 + j
    txn_date = random_date(TXN_DATE_START, TXN_DATE_END)
    product_id = random.choice(VALID_PRODUCT_IDS[:18])
    store_mismatch_rows.append(Row(
        transaction_id=f"T{str(i).zfill(5)}",
        transaction_timestamp=random_timestamp(txn_date),
        store_id=f"S{str(900 + j).zfill(3)}",  # マスター未登録の店舗ID
        product_id=product_id,
        customer_id=random.choice(VALID_CUSTOMER_IDS),
        quantity=random.randint(1, 5),
        unit_price=PRODUCT_PRICE.get(product_id, 500.0),
    ))

# --- 取引ID重複 8件（正常データの先頭8件をそのまま複製） ---
duplicate_rows = normal_rows[:8]

# --- 数量異常 8件（0件:4件、負値:4件） ---
quantity_anomaly_rows = []
for j in range(8):
    i = 157 + j
    txn_date = random_date(TXN_DATE_START, TXN_DATE_END)
    product_id = random.choice(VALID_PRODUCT_IDS[:18])
    qty = 0 if j % 2 == 0 else -random.randint(1, 5)
    quantity_anomaly_rows.append(Row(
        transaction_id=f"T{str(i).zfill(5)}",
        transaction_timestamp=random_timestamp(txn_date),
        store_id=random.choice(VALID_STORE_IDS),
        product_id=product_id,
        customer_id=random.choice(VALID_CUSTOMER_IDS),
        quantity=qty,
        unit_price=PRODUCT_PRICE.get(product_id, 500.0),
    ))

# --- 単価異常 8件（null:4件、負値:4件） ---
price_anomaly_rows = []
for j in range(8):
    i = 165 + j
    txn_date = random_date(TXN_DATE_START, TXN_DATE_END)
    product_id = random.choice(VALID_PRODUCT_IDS[:18])
    price = None if j % 2 == 0 else -round(random.uniform(100, 3000), 0)
    price_anomaly_rows.append(Row(
        transaction_id=f"T{str(i).zfill(5)}",
        transaction_timestamp=random_timestamp(txn_date),
        store_id=random.choice(VALID_STORE_IDS),
        product_id=product_id,
        customer_id=random.choice(VALID_CUSTOMER_IDS),
        quantity=random.randint(1, 5),
        unit_price=price,
    ))

# --- タイムスタンプ表記揺れ 8件（フォーマット/timezone混在） ---
TIMESTAMP_VARIANTS = [
    lambda d: d.strftime("%Y/%m/%d %H:%M"),                       # スラッシュ区切り・秒なし
    lambda d: d.strftime("%d-%m-%Y %H:%M:%S"),                    # 日-月-年順
    lambda d: d.strftime("%Y-%m-%dT%H:%M:%S+09:00"),              # ISO8601 + JSTオフセット
    lambda d: d.strftime("%Y-%m-%d %H:%M:%S JST"),                # タイムゾーン名付き
    lambda d: d.strftime("%Y%m%d%H%M%S"),                         # 区切りなし数値羅列
    lambda d: d.strftime("%Y-%m-%dT%H:%M:%SZ"),                   # UTC表記（Zサフィックス）
    lambda d: d.strftime("%m/%d/%Y %I:%M %p"),                    # 米国式12時間表記
    lambda d: d.strftime("%Y-%m-%d %H:%M:%S.%f"),                 # マイクロ秒付き
]
timestamp_irregular_rows = []
for j in range(8):
    i = 173 + j
    txn_date = random_date(TXN_DATE_START, TXN_DATE_END)
    h = random.randint(9, 20)
    m = random.randint(0, 59)
    dt_obj = _dt.datetime(txn_date.year, txn_date.month, txn_date.day, h, m, random.randint(0, 59))
    product_id = random.choice(VALID_PRODUCT_IDS[:18])
    timestamp_irregular_rows.append(Row(
        transaction_id=f"T{str(i).zfill(5)}",
        transaction_timestamp=TIMESTAMP_VARIANTS[j](dt_obj),
        store_id=random.choice(VALID_STORE_IDS),
        product_id=product_id,
        customer_id=random.choice(VALID_CUSTOMER_IDS),
        quantity=random.randint(1, 5),
        unit_price=PRODUCT_PRICE.get(product_id, 500.0),
    ))

# --- 会員ID欠損 12件（非会員取引） ---
customer_null_rows = []
for j in range(12):
    i = 181 + j
    txn_date = random_date(TXN_DATE_START, TXN_DATE_END)
    product_id = random.choice(VALID_PRODUCT_IDS[:18])
    customer_null_rows.append(Row(
        transaction_id=f"T{str(i).zfill(5)}",
        transaction_timestamp=random_timestamp(txn_date),
        store_id=random.choice(VALID_STORE_IDS),
        product_id=product_id,
        customer_id=None,  # 非会員取引
        quantity=random.randint(1, 5),
        unit_price=PRODUCT_PRICE.get(product_id, 500.0),
    ))

all_pos_rows = (
    normal_rows
    + product_mismatch_rows
    + store_mismatch_rows
    + duplicate_rows
    + quantity_anomaly_rows
    + price_anomaly_rows
    + timestamp_irregular_rows
    + customer_null_rows
)
df_pos = spark.createDataFrame(all_pos_rows, schema=pos_schema)

print(f"=== POSトランザクション（合計 {df_pos.count()} 件） ===")
df_pos.show(20, truncate=False)


# ──────────────────────────────────────────────
# 5. データ品質サマリー
# ──────────────────────────────────────────────

from pyspark.sql import functions as F

print("\n" + "=" * 50)
print("=== データ品質サマリー ===")
print("=" * 50)

total_pos = df_pos.count()
print(f"POSトランザクション総件数: {total_pos} 件")

# 商品マスター不整合
product_ids_master = [r.product_id for r in df_products.select("product_id").collect()]
product_mismatch_count = df_pos.filter(~F.col("product_id").isin(product_ids_master)).count()
print(f"商品マスター不整合: {product_mismatch_count} 件")

# 店舗マスター不整合
store_ids_master = [r.store_id for r in df_stores.select("store_id").collect()]
store_mismatch_count = df_pos.filter(~F.col("store_id").isin(store_ids_master)).count()
print(f"店舗マスター不整合: {store_mismatch_count} 件")

# 取引ID重複
dup_groups = df_pos.groupBy("transaction_id").count().filter(F.col("count") > 1)
dup_group_count = dup_groups.count()
dup_row_count = dup_groups.agg(F.sum("count")).collect()[0][0] or 0
print(f"取引ID重複: {dup_group_count} 件のIDが重複（重複関係にある行数の合計: {dup_row_count} 行）")

# 数量異常
quantity_anomaly_count = df_pos.filter((F.col("quantity") <= 0) | F.col("quantity").isNull()).count()
print(f"数量異常（0または負値）: {quantity_anomaly_count} 件")

# 単価異常
price_anomaly_count = df_pos.filter(F.col("unit_price").isNull() | (F.col("unit_price") < 0)).count()
print(f"単価異常（nullまたは負値）: {price_anomaly_count} 件")

# 会員ID欠損
customer_null_count = df_pos.filter(F.col("customer_id").isNull()).count()
print(f"会員ID欠損（非会員取引）: {customer_null_count} 件")

# 商品カテゴリnull（商品マスター側の品質課題）
category_null_count = df_products.filter(F.col("product_category").isNull()).count()
print(f"商品カテゴリ未設定（商品マスター）: {category_null_count} 件 / {df_products.count()} 件")

print("\n※ transaction_timestamp のフォーマット/timezone揺れは 8 件（T00173〜T00180）")
print("  StringType のまま保持しているため件数はSilverでのパース時に検出する想定")


# ──────────────────────────────────────────────
# 6. Spark テンポラリビューとして登録
# ──────────────────────────────────────────────

df_stores.createOrReplaceTempView("store_master")
df_products.createOrReplaceTempView("product_master")
df_members.createOrReplaceTempView("member_master")
df_pos.createOrReplaceTempView("pos_transactions")

print("\nテンポラリビューを登録しました: store_master / product_master / member_master / pos_transactions")
print("例: spark.sql('SELECT * FROM pos_transactions LIMIT 10').show()")


# ──────────────────────────────────────────────
# 7. Delta保存（Unity Catalog Volume/Hiveメタストアを使う場合のみ有効化）
#    save_bronze_delta_tables.py と同様に bronze データベースへ保存する場合は
#    以下を参考にコメントを外して利用する
# ──────────────────────────────────────────────

# spark.sql("CREATE DATABASE IF NOT EXISTS bronze")
# df_stores.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable("bronze.bronze_store_master")
# df_products.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable("bronze.bronze_product_master")
# df_members.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable("bronze.bronze_member_master")
# df_pos.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable("bronze.bronze_pos_transactions")

print("\n=== 全データ生成完了 ===")
# spark.stop() はここで呼ばない
# Databricks ノートブックでは SparkSession はクラスター側が管理するため、
# stop() を呼ぶと後続セルで NO_ACTIVE_SESSION エラーが発生する
