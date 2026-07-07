"""
小売メダリオンアーキテクチャ Bronze レイヤー サンプルデータ生成スクリプト
=====================================================================
対象データソース（4表。今回はこの4表のみを設計・生成する）
  1. POSトランザクション          : bronze_pos_transactions（24件）
  2. 商品マスター                  : bronze_product_master（6件）
  3. 店舗マスター                  : bronze_store_master（3件）
  4. 会員マスター                  : bronze_customer_master（5件）

Gold レイヤーで必要になる集計（daily sales kpi / 店舗別売上 / カテゴリー別売上 /
データ品質サマリ）を日次・店舗・カテゴリーの3軸で成立させるため、
POSトランザクションは 2024-06-01〜2024-06-03 の3日間 × 3店舗 × 複数カテゴリー
の組み合わせを最小限のパターンで網羅している。

また #データ品質課題 に列挙された8種類の課題を、判別しやすいよう
1レコード（または1マスター行）に1課題ずつ意図的に混入させている
（件数はコード内コメントおよび本スクリプト末尾の品質サマリー出力を参照）。

動作確認環境：Databricks Free Edition（Unity Catalog 不使用・Hive メタストア）
Databricks ノートブックでは spark はクラスターから自動注入されるため、
SparkSession.builder は呼ばない（呼ぶと INVALID_CONNECT_URL エラーになる）。
"""

from pyspark.sql import Row
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, DoubleType, DateType
)
from pyspark.sql import functions as F
from datetime import date


# ──────────────────────────────────────────────
# 0. スキーマ設計を表示するための補助関数
#    （データ型・nullable・列説明を表形式でまとめて出力する）
# ──────────────────────────────────────────────

def print_table_design(table_name: str, schema: StructType, descriptions: dict) -> None:
    """表設計（列名・データ型・nullable・説明）を整形して表示する"""
    print(f"\n=== 表設計: {table_name} ===")
    print(f"{'列名':<24}{'データ型':<12}{'nullable':<10}説明")
    print("-" * 100)
    for field in schema.fields:
        print(
            f"{field.name:<24}{field.dataType.simpleString():<12}"
            f"{str(field.nullable):<10}{descriptions.get(field.name, '')}"
        )


# ──────────────────────────────────────────────
# 1. 商品マスター（6件、うち1件はカテゴリーNULLの品質課題）
# ──────────────────────────────────────────────

product_schema = StructType([
    StructField("product_id",       StringType(), nullable=False),  # 商品ID（主キー）
    StructField("product_name",     StringType(), nullable=False),  # 商品名
    StructField("product_category", StringType(), nullable=True),   # 商品カテゴリー（品質課題：NULLを含む）
])

PRODUCT_MASTER_DESC = {
    "product_id": "商品ID（主キー）。POSトランザクションの product_id と紐付ける",
    "product_name": "商品名",
    "product_category": "商品カテゴリー（食品/飲料/日用品）。品質課題としてカテゴリーNULLの商品を1件含む",
}

PRODUCT_ROWS = [
    ("P001", "おにぎり",     "食品"),
    ("P002", "サンドイッチ", "食品"),
    ("P003", "コーヒー",     "飲料"),
    ("P004", "緑茶",         "飲料"),
    ("P005", "ノート",       "日用品"),
    ("P006", "消しゴム",     None),  # 品質課題：product_categoryがNULL
]

df_products = spark.createDataFrame(
    [Row(product_id=p, product_name=n, product_category=c) for p, n, c in PRODUCT_ROWS],
    schema=product_schema,
)


# ──────────────────────────────────────────────
# 2. 店舗マスター（3件、品質課題なし）
# ──────────────────────────────────────────────

store_schema = StructType([
    StructField("store_id",   StringType(), nullable=False),  # 店舗ID（主キー）
    StructField("store_name", StringType(), nullable=False),  # 店舗名
    StructField("store_area", StringType(), nullable=True),   # 店舗所在地域
])

STORE_MASTER_DESC = {
    "store_id": "店舗ID（主キー）。POSトランザクションの store_id と紐付ける",
    "store_name": "店舗名",
    "store_area": "店舗所在地域（例：関東、近畿、中部）。店舗別・地域別集計の補助情報",
}

STORE_ROWS = [
    ("S001", "渋谷店", "関東"),
    ("S002", "難波店", "近畿"),
    ("S003", "栄店",   "中部"),
]

df_stores = spark.createDataFrame(
    [Row(store_id=s, store_name=n, store_area=a) for s, n, a in STORE_ROWS],
    schema=store_schema,
)


# ──────────────────────────────────────────────
# 3. 会員マスター（5件、品質課題なし）
# ──────────────────────────────────────────────

customer_schema = StructType([
    StructField("customer_id",       StringType(), nullable=False),  # 会員ID（主キー）
    StructField("customer_name",     StringType(), nullable=False),  # 会員氏名
    StructField("registration_date", DateType(),   nullable=True),   # 会員登録日
])

CUSTOMER_MASTER_DESC = {
    "customer_id": "会員ID（主キー）。POSトランザクションの customer_id と紐付ける",
    "customer_name": "会員氏名",
    "registration_date": "会員登録日",
}

CUSTOMER_ROWS = [
    ("C001", "山田太郎", date(2023, 4, 1)),
    ("C002", "佐藤花子", date(2023, 6, 15)),
    ("C003", "鈴木一郎", date(2023, 9, 10)),
    ("C004", "田中美咲", date(2024, 1, 5)),
    ("C005", "高橋健二", date(2024, 2, 20)),
]

df_customers = spark.createDataFrame(
    [Row(customer_id=c, customer_name=n, registration_date=d) for c, n, d in CUSTOMER_ROWS],
    schema=customer_schema,
)


# ──────────────────────────────────────────────
# 4. POSトランザクション（24件）
#    2024-06-01〜2024-06-03 の3日間 × 3店舗 × 複数カテゴリーで正常データを構成し、
#    #データ品質課題 に列挙された8種類の課題を1件ずつ判別可能な形で混入させる。
#
#    transaction_timestamp は意図的に StringType のまま保持する。
#    Bronzeレイヤーではソースの生表記（ISO8601+09:00 / UTC Z表記 / スラッシュ区切り等）
#    を変換せずに取り込み、フォーマット・タイムゾーンの揺れをSilverレイヤーで
#    正規化する方針のため（TimestampType にすると取り込み時点でパース不能な
#    表記がエラー/NULL化してしまい、揺れそのものを検知できなくなる）。
# ──────────────────────────────────────────────

pos_schema = StructType([
    StructField("transaction_id",        StringType(),  nullable=False),  # 取引ID
    StructField("transaction_timestamp", StringType(),  nullable=False),  # 取引日時（生文字列）
    StructField("store_id",              StringType(),  nullable=False),  # 店舗ID（外部キー）
    StructField("product_id",            StringType(),  nullable=False),  # 商品ID（外部キー）
    StructField("customer_id",           StringType(),  nullable=True),   # 会員ID（非会員はNULL）
    StructField("quantity",              IntegerType(), nullable=False),  # 購買数量
    StructField("unit_price",            DoubleType(),  nullable=True),   # 単価（円）
])

POS_DESC = {
    "transaction_id": "取引ID。本来は一意だが、システム障害等による重複混入を品質課題として1組（2件）含む",
    "transaction_timestamp": "取引日時（文字列型）。フォーマット/タイムゾーン表記の揺れ"
                              "（ISO8601+09:00、UTC Z表記、スラッシュ区切り等）を生データのまま保持する",
    "store_id": "店舗ID（外部キー）。店舗マスターに存在しないIDの混入を品質課題として1件含む",
    "product_id": "商品ID（外部キー）。商品マスターに存在しないIDの混入を品質課題として1件含む",
    "customer_id": "会員ID（外部キー）。非会員購買等でNULLになる取引を品質課題として2件含む",
    "quantity": "購買数量。0または負数となる異常値を品質課題として2件（0件・負数各1件）含む",
    "unit_price": "単価（円）。NULLまたは負数となる異常値を品質課題として2件（NULL・負数各1件）含む",
}

# (transaction_id, transaction_timestamp, store_id, product_id, customer_id, quantity, unit_price)
POS_ROWS = [
    # --- 正常データ 15件（3日間 × 3店舗 × 複数カテゴリー） ---
    ("TXN0001", "2024-06-01T09:15:00+09:00", "S001", "P001", "C001", 2, 150.0),
    ("TXN0002", "2024-06-01T10:30:00+09:00", "S001", "P003", "C002", 1, 320.0),
    ("TXN0003", "2024-06-01T11:05:00+09:00", "S002", "P002", "C003", 3, 280.0),
    ("TXN0004", "2024-06-01T13:45:00+09:00", "S002", "P005", None,   1, 120.0),  # 品質課題: customer_id NULL
    ("TXN0005", "2024-06-01T14:20:00+09:00", "S003", "P004", "C001", 2, 250.0),
    ("TXN0006", "2024-06-01T18:10:00+09:00", "S003", "P001", "C004", 1, 150.0),
    ("TXN0007", "2024-06-02T08:50:00+09:00", "S001", "P002", "C002", 2, 280.0),
    ("TXN0008", "2024-06-02T09:40:00+09:00", "S001", "P004", "C003", 1, 250.0),
    ("TXN0009", "2024-06-02T12:15:00+09:00", "S002", "P001", "C005", 4, 150.0),
    ("TXN0010", "2024-06-02T15:00:00+09:00", "S002", "P006", "C001", 1, 100.0),
    ("TXN0011", "2024-06-02T16:30:00+09:00", "S003", "P003", None,   2, 320.0),  # 品質課題: customer_id NULL
    ("TXN0012", "2024-06-02T19:05:00+09:00", "S003", "P005", "C002", 1, 120.0),
    ("TXN0013", "2024-06-03T09:00:00+09:00", "S001", "P001", "C003", 3, 150.0),
    ("TXN0014", "2024-06-03T10:20:00+09:00", "S002", "P003", "C004", 2, 320.0),
    ("TXN0015", "2024-06-03T13:00:00+09:00", "S003", "P002", "C005", 1, 280.0),

    # --- 品質課題データ 9件 ---
    ("TXN0001", "2024-06-01T09:15:00+09:00", "S001", "P001", "C001", 2, 150.0),   # 品質課題: transaction_id重複（TXN0001と同一）
    ("TXN0016", "2024-06-01T20:00:00+09:00", "S001", "P999", "C001", 1, 200.0),   # 品質課題: product_idが商品マスターに存在しない
    ("TXN0017", "2024-06-02T20:30:00+09:00", "S999", "P002", "C002", 1, 280.0),   # 品質課題: store_idが店舗マスターに存在しない
    ("TXN0018", "2024-06-01T21:00:00+09:00", "S002", "P004", "C003", 0, 250.0),   # 品質課題: quantity=0
    ("TXN0019", "2024-06-02T21:15:00+09:00", "S003", "P001", "C004", -3, 150.0),  # 品質課題: quantityが負数
    ("TXN0020", "2024-06-03T14:00:00+09:00", "S001", "P003", "C005", 2, None),    # 品質課題: unit_priceがNULL
    ("TXN0021", "2024-06-03T15:30:00+09:00", "S002", "P005", "C001", 1, -120.0),  # 品質課題: unit_priceが負数
    ("TXN0022", "2024/06/03 16:00",           "S003", "P006", "C002", 1, 100.0),  # 品質課題: timestampフォーマット揺れ（スラッシュ区切り）
    ("TXN0023", "2024-06-03T07:45:00Z",       "S001", "P002", "C003", 2, 280.0),  # 品質課題: timestampタイムゾーン表記揺れ（UTC Z表記）
]

df_pos = spark.createDataFrame(
    [
        Row(
            transaction_id=t, transaction_timestamp=ts, store_id=st,
            product_id=p, customer_id=c, quantity=q, unit_price=up,
        )
        for t, ts, st, p, c, q, up in POS_ROWS
    ],
    schema=pos_schema,
)


# ──────────────────────────────────────────────
# 5. Output 1: 表設計（データ型・nullable・列説明）の表示
# ──────────────────────────────────────────────

print_table_design("bronze_product_master", product_schema, PRODUCT_MASTER_DESC)
print_table_design("bronze_store_master", store_schema, STORE_MASTER_DESC)
print_table_design("bronze_customer_master", customer_schema, CUSTOMER_MASTER_DESC)
print_table_design("bronze_pos_transactions", pos_schema, POS_DESC)

print("\n=== サンプルデータ確認 ===")
print("--- bronze_product_master ---")
df_products.show(truncate=False)
print("--- bronze_store_master ---")
df_stores.show(truncate=False)
print("--- bronze_customer_master ---")
df_customers.show(truncate=False)
print("--- bronze_pos_transactions ---")
df_pos.orderBy("transaction_id").show(30, truncate=False)


# ──────────────────────────────────────────────
# 6. Output 2: 全件数 / 品質課題件数 / 品質課題説明の表示
# ──────────────────────────────────────────────

valid_product_ids = [r.product_id for r in df_products.select("product_id").collect()]
valid_store_ids = [r.store_id for r in df_stores.select("store_id").collect()]

# ISO8601 + 日本時間オフセット(+09:00) 形式に一致しないものを「表記揺れ」とみなす
TIMESTAMP_PATTERN = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+09:00$"

dq_checks = [
    ("product_idが商品マスターに存在しない",
     df_pos.filter(~F.col("product_id").isin(valid_product_ids))),
    ("store_idが店舗マスターに存在しない",
     df_pos.filter(~F.col("store_id").isin(valid_store_ids))),
    ("transaction_idの重複",
     df_pos.join(
         df_pos.groupBy("transaction_id").count().filter(F.col("count") > 1).select("transaction_id"),
         on="transaction_id", how="inner",
     )),
    ("quantityが0または負数",
     df_pos.filter(F.col("quantity") <= 0)),
    ("unit_priceがNULLまたは負数",
     df_pos.filter(F.col("unit_price").isNull() | (F.col("unit_price") < 0))),
    ("transaction_timestampの表記が揺れている",
     df_pos.filter(~F.col("transaction_timestamp").rlike(TIMESTAMP_PATTERN))),
    ("customer_idがNULL",
     df_pos.filter(F.col("customer_id").isNull())),
    ("product_categoryがNULL（商品マスター側）",
     df_products.filter(F.col("product_category").isNull())),
]

print("\n=== Output 2: 全件数・品質課題件数サマリー ===")
print(f"bronze_pos_transactions   全件数: {df_pos.count()} 件")
print(f"bronze_product_master     全件数: {df_products.count()} 件")
print(f"bronze_store_master       全件数: {df_stores.count()} 件")
print(f"bronze_customer_master    全件数: {df_customers.count()} 件")

print("\n--- 品質課題別 件数 ---")
for label, dq_df in dq_checks:
    print(f"[{dq_df.count()} 件] {label}")

print("\n--- 品質課題レコード詳細 ---")
for label, dq_df in dq_checks:
    print(f"\n# {label}")
    dq_df.show(truncate=False)


# ──────────────────────────────────────────────
# 7. テンポラリビュー登録（同一セッション内でSQL参照可能にする）
# ──────────────────────────────────────────────

df_products.createOrReplaceTempView("product_master")
df_stores.createOrReplaceTempView("store_master")
df_customers.createOrReplaceTempView("customer_master")
df_pos.createOrReplaceTempView("pos_transactions")

print("\nテンポラリビューを登録しました: product_master / store_master / customer_master / pos_transactions")
print("\n=== サンプルデータ生成完了 ===")
# spark.stop() はここで呼ばない
# Databricks ノートブックでは SparkSession はクラスター側が管理するため、
# stop() を呼ぶと後続セルで NO_ACTIVE_SESSION エラーが発生する
