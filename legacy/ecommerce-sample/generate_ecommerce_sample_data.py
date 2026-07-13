"""
ECサイト サンプルデータ生成スクリプト
- 売上トランザクション：1000件（重複5件・欠損10件・マスター不一致5件を含む）
- 商品マスター：20件
- ユーザーマスター：100件
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
# 1. 商品マスター（20件）
# ──────────────────────────────────────────────

# カテゴリと商品名の定義
PRODUCT_CATALOG = [
    ("P001", "ワイヤレスイヤホン",     "家電"),
    ("P002", "スマートウォッチ",       "家電"),
    ("P003", "ノートパソコン",         "家電"),
    ("P004", "USBハブ",               "家電"),
    ("P005", "モバイルバッテリー",     "家電"),
    ("P006", "綿100%Tシャツ",         "衣類"),
    ("P007", "デニムジーンズ",         "衣類"),
    ("P008", "レインコート",           "衣類"),
    ("P009", "スニーカー",             "衣類"),
    ("P010", "ウールセーター",         "衣類"),
    ("P011", "プロテインパウダー",     "食品"),
    ("P012", "オーガニックコーヒー",   "食品"),
    ("P013", "抹茶クッキー",           "食品"),
    ("P014", "グラノーラ",             "食品"),
    ("P015", "ドライフルーツMIX",      "食品"),
    ("P016", "ヨガマット",             "スポーツ"),
    ("P017", "ダンベルセット",         "スポーツ"),
    ("P018", "ランニングシューズ",     "スポーツ"),
    ("P019", "水筒（500ml）",          "スポーツ"),
    ("P020", "フィットネスバンド",     "スポーツ"),
]

# 商品マスターのスキーマ定義
product_schema = StructType([
    StructField("product_id",   StringType(), nullable=False),  # 商品ID（主キー）
    StructField("product_name", StringType(), nullable=True),   # 商品名
    StructField("category",     StringType(), nullable=True),   # カテゴリ
])

# 商品マスター DataFrame 作成
product_rows = [Row(product_id=pid, product_name=name, category=cat)
                for pid, name, cat in PRODUCT_CATALOG]
df_products = spark.createDataFrame(product_rows, schema=product_schema)

print("=== 商品マスター（20件） ===")
df_products.show(truncate=False)


# ──────────────────────────────────────────────
# 2. ユーザーマスター（100件）
# ──────────────────────────────────────────────

# 地域リスト
REGIONS = ["北海道", "東北", "関東", "中部", "近畿", "中国", "四国", "九州"]

# 日本語名のサンプル（姓・名）
LAST_NAMES  = ["田中", "鈴木", "佐藤", "山田", "伊藤", "渡辺", "中村", "小林",
               "加藤", "吉田", "山口", "松本", "井上", "木村", "林", "斎藤",
               "清水", "山本", "池田", "橋本"]
FIRST_NAMES = ["太郎", "花子", "次郎", "美咲", "健一", "由美", "翔", "あゆみ",
               "大輔", "さくら", "裕子", "誠", "和子", "拓海", "麻衣", "直樹",
               "恵子", "亮", "奈々", "隆"]

# ユーザーマスターのスキーマ定義
user_schema = StructType([
    StructField("user_id",   StringType(), nullable=False),  # ユーザーID（主キー）
    StructField("user_name", StringType(), nullable=True),   # ユーザー名
    StructField("region",    StringType(), nullable=True),   # 居住地域
])

# 100件のユーザーデータ生成
user_rows = [
    Row(
        user_id=f"U{str(i).zfill(3)}",                              # U001〜U100
        user_name=random.choice(LAST_NAMES) + random.choice(FIRST_NAMES),  # 姓名結合
        region=random.choice(REGIONS),                               # ランダム地域
    )
    for i in range(1, 101)
]
df_users = spark.createDataFrame(user_rows, schema=user_schema)

print("=== ユーザーマスター（100件） ===")
df_users.show(20, truncate=False)


# ──────────────────────────────────────────────
# 3. 売上トランザクション（1000件）
#    ・重複5件：既存レコードをそのままコピー
#    ・欠損10件：amount または order_date を None にする
#    ・マスター不一致5件：存在しない product_id を使用
# ──────────────────────────────────────────────

# 注文日の範囲（2024年1月1日〜2024年12月31日）
DATE_START = date(2024, 1, 1)
DATE_END   = date(2024, 12, 31)

# 売上トランザクションのスキーマ定義
order_schema = StructType([
    StructField("order_id",   StringType(),  nullable=False),  # 注文ID
    StructField("user_id",    StringType(),  nullable=True),   # ユーザーID（外部キー）
    StructField("product_id", StringType(),  nullable=True),   # 商品ID（外部キー）
    StructField("amount",     DoubleType(),  nullable=True),   # 注文金額（円）
    StructField("order_date", DateType(),    nullable=True),   # 注文日
])

# --- 正常レコード 980件 生成 ---
normal_rows = []
for i in range(1, 981):
    order_id   = f"ORD{str(i).zfill(5)}"                        # ORD00001〜ORD00980
    user_id    = f"U{str(random.randint(1, 100)).zfill(3)}"     # U001〜U100 からランダム選択
    product_id = f"P{str(random.randint(1, 20)).zfill(3)}"      # P001〜P020 からランダム選択
    amount     = round(random.uniform(500, 50000), 0)            # 500〜50,000円
    order_date = random_date(DATE_START, DATE_END)               # ランダム注文日

    normal_rows.append(Row(
        order_id=order_id,
        user_id=user_id,
        product_id=product_id,
        amount=amount,
        order_date=order_date,
    ))

# --- 重複5件：先頭5件と同じ内容をコピー（order_id も同じにして重複を表現） ---
duplicate_rows = normal_rows[:5]  # 先頭5件を丸ごとコピー

# --- 欠損10件：amount=None または order_date=None を交互に設定 ---
missing_rows = []
for j in range(10):
    base_i     = 981 + j
    order_id   = f"ORD{str(base_i).zfill(5)}"
    user_id    = f"U{str(random.randint(1, 100)).zfill(3)}"
    product_id = f"P{str(random.randint(1, 20)).zfill(3)}"

    if j % 2 == 0:
        # 偶数インデックス：金額が欠損
        missing_rows.append(Row(
            order_id=order_id, user_id=user_id, product_id=product_id,
            amount=None,                          # 金額欠損
            order_date=random_date(DATE_START, DATE_END),
        ))
    else:
        # 奇数インデックス：注文日が欠損
        missing_rows.append(Row(
            order_id=order_id, user_id=user_id, product_id=product_id,
            amount=round(random.uniform(500, 50000), 0),
            order_date=None,                      # 注文日欠損
        ))

# --- マスター不一致5件：商品マスターに存在しない product_id を使用 ---
unmatched_rows = []
for k in range(5):
    base_i     = 991 + k
    order_id   = f"ORD{str(base_i).zfill(5)}"
    user_id    = f"U{str(random.randint(1, 100)).zfill(3)}"
    product_id = f"P{str(99 + k).zfill(3)}"     # P099〜P103：商品マスターに存在しないID

    unmatched_rows.append(Row(
        order_id=order_id,
        user_id=user_id,
        product_id=product_id,                    # 存在しない商品ID（マスター不一致）
        amount=round(random.uniform(500, 50000), 0),
        order_date=random_date(DATE_START, DATE_END),
    ))

# --- 全レコードを結合して DataFrame 作成 ---
all_order_rows = normal_rows + duplicate_rows + missing_rows + unmatched_rows
df_orders = spark.createDataFrame(all_order_rows, schema=order_schema)

print(f"=== 売上トランザクション（合計 {df_orders.count()} 件） ===")
df_orders.show(20, truncate=False)


# ──────────────────────────────────────────────
# 4. データ品質の確認
# ──────────────────────────────────────────────

print("=== データ品質サマリー ===")

# 重複件数：order_id が重複しているレコード数
from pyspark.sql import functions as F

dup_count = df_orders.groupBy("order_id").count().filter(F.col("count") > 1)
print(f"重複 order_id 件数: {dup_count.count()} 件")
dup_count.show(truncate=False)

# 欠損件数：amount または order_date が NULL のレコード数
null_amount = df_orders.filter(F.col("amount").isNull()).count()
null_date   = df_orders.filter(F.col("order_date").isNull()).count()
print(f"amount 欠損: {null_amount} 件 / order_date 欠損: {null_date} 件")

# マスター不一致件数：商品マスターに存在しない product_id
valid_product_ids = [row.product_id for row in df_products.select("product_id").collect()]
unmatched_count = df_orders.filter(~F.col("product_id").isin(valid_product_ids)).count()
print(f"商品マスター不一致: {unmatched_count} 件")

# 不一致レコードの表示
df_orders.filter(~F.col("product_id").isin(valid_product_ids)).show(truncate=False)


# ──────────────────────────────────────────────
# 5. Spark テンポラリビューとして登録（Databricks / ローカル共通）
#    ※ パブリック DBFS ルートが無効な Databricks 環境では
#      /tmp への Parquet 書き込みが禁止されるため、
#      テンポラリビューを使用してセッション内で SQL 参照できるようにする
# ──────────────────────────────────────────────

# テンポラリビューとして登録（同一 SparkSession 内で SQL クエリ可能）
df_products.createOrReplaceTempView("products")
df_users.createOrReplaceTempView("users")
df_orders.createOrReplaceTempView("orders")

print("テンポラリビューを登録しました: products / users / orders")
print("例: spark.sql('SELECT * FROM orders LIMIT 10').show()")

# ──────────────────────────────────────────────
# 6. Parquet 保存（Unity Catalog Volume を使う場合のみ有効化）
#    Databricks: Unity Catalog が有効な環境では以下のパスを使用
#    例） /Volumes/<catalog>/<schema>/<volume>/ecommerce_sample
#
#    ローカル Spark の場合は OUTPUT_DIR を任意のローカルパスに変更する
# ──────────────────────────────────────────────

# ▼ 保存する場合は OUTPUT_DIR を環境に合わせて変更し、コメントを外してください
# OUTPUT_DIR = "/Volumes/your_catalog/your_schema/your_volume/ecommerce_sample"  # Databricks Unity Catalog
# OUTPUT_DIR = "./ecommerce_sample"  # ローカル Spark

# df_products.write.mode("overwrite").parquet(f"{OUTPUT_DIR}/products")
# df_users.write.mode("overwrite").parquet(f"{OUTPUT_DIR}/users")
# df_orders.write.mode("overwrite").parquet(f"{OUTPUT_DIR}/orders")
# print(f"データを保存しました: {OUTPUT_DIR}")

print("\n=== 全データ生成完了 ===")
# spark.stop() はここで呼ばない
# Databricks ノートブックでは SparkSession はクラスター側が管理するため、
# stop() を呼ぶと後続セルで NO_ACTIVE_SESSION エラーが発生する
