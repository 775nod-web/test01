"""
小売メダリオンアーキテクチャ Gold layer 表定義スクリプト（Databricks Free Edition想定）
==================================================================

■ ビジネス目的
    店舗・商品別の売上を可視化し、売上低下や人気商品の傾向を早期に把握する

■ 想定利用者
    本社営業管理 / 店長 / 商品企画 / データサイエンスチーム

■ 今回のスコープ
    Gold layerの表定義（スキーマ）のみを確定し、データの入っていない空表として
    `gold` スキーマに保存する。sample.pos_sales 等からのクレンジング・集計処理は
    後続タスクで対応する。

■ 今回作成する Gold layer 表（Knowledge base記載の4表のみ）
    1. gold_daily_store_sales         … 日別店舗別売上
    2. gold_category_sales            … 商品カテゴリ別売上
    3. gold_store_ranking              … 店舗ランキング
    4. gold_unregistered_master_report … マスター未登録レポート

Databricks ノートブックでは spark はクラスターから自動注入されるため
SparkSession.builder は呼ばない。
"""

from pyspark.sql.types import StructType, StructField, StringType


# ================================================================
# Output 1: Gold layer 表設計
# ================================================================

gold_table_overview = [
    ("gold_daily_store_sales",
     "sales_date × store_id（日付・店舗の組み合わせで1行）",
     "日次×店舗単位の売上推移を可視化し、特定店舗の売上低下を早期に検知する（本社営業管理・店長向け）"),
    ("gold_category_sales",
     "category（商品カテゴリ単位で1行、対象期間の累計）",
     "商品カテゴリ別の売上構成を把握し、人気・不振カテゴリの傾向を捉える（商品企画・データサイエンスチーム向け）"),
    ("gold_store_ranking",
     "store_id（店舗単位で1行、対象期間の累計＋売上ランキング）",
     "店舗を売上順にランキングし、優良店舗・要テコ入れ店舗を経営層が一目で把握できるようにする（本社営業管理向け）"),
    ("gold_unregistered_master_report",
     "transaction_id（store_idまたはproduct_idがマスター未登録の取引のみ、1取引1行）",
     "マスターに存在しない店舗／商品を含む取引を可視化し、データ品質是正のフォローアップ対象を明確にする（データサイエンスチーム・本社向け）"),
]
overview_schema = StructType([
    StructField("table_name", StringType()),
    StructField("grain",      StringType()),
    StructField("purpose",    StringType()),
])
df_gold_overview = spark.createDataFrame(gold_table_overview, schema=overview_schema)

print("=" * 80)
print("Output 1-a: Gold layer 表一覧（表名・粒度・目的）")
print("=" * 80)
df_gold_overview.show(20, truncate=False)

gold_column_design = [
    ("gold_daily_store_sales", "sales_date",          "DateType",   "NOT NULL", "売上日（transaction_datetimeを日付に正規化）"),
    ("gold_daily_store_sales", "store_id",            "StringType", "NOT NULL", "店舗ID"),
    ("gold_daily_store_sales", "store_name",          "StringType", "NOT NULL", "店舗名（store_masterから付与）"),
    ("gold_daily_store_sales", "region",              "StringType", "NOT NULL", "地域（store_masterから付与）"),
    ("gold_daily_store_sales", "transaction_count",   "LongType",   "NOT NULL", "取引件数（重複transactionは除去済み）"),
    ("gold_daily_store_sales", "total_quantity",      "LongType",   "NOT NULL", "販売数量合計"),
    ("gold_daily_store_sales", "total_sales_amount",  "DoubleType", "NOT NULL", "売上金額合計（円）"),

    ("gold_category_sales", "category",            "StringType", "NOT NULL", "商品カテゴリ"),
    ("gold_category_sales", "product_count",       "LongType",   "NOT NULL", "カテゴリに属するマスター登録商品数"),
    ("gold_category_sales", "transaction_count",   "LongType",   "NOT NULL", "取引件数"),
    ("gold_category_sales", "total_quantity",      "LongType",   "NOT NULL", "販売数量合計"),
    ("gold_category_sales", "total_sales_amount",  "DoubleType", "NOT NULL", "売上金額合計（円）"),

    ("gold_store_ranking", "sales_rank",          "IntegerType", "NOT NULL", "売上金額に基づく店舗ランキング（1位が最高売上）"),
    ("gold_store_ranking", "store_id",            "StringType",  "NOT NULL", "店舗ID"),
    ("gold_store_ranking", "store_name",          "StringType",  "NOT NULL", "店舗名"),
    ("gold_store_ranking", "region",              "StringType",  "NOT NULL", "地域"),
    ("gold_store_ranking", "store_type",          "StringType",  "NOT NULL", "店舗タイプ"),
    ("gold_store_ranking", "total_sales_amount",  "DoubleType",  "NOT NULL", "売上金額合計（円）"),
    ("gold_store_ranking", "total_quantity",      "LongType",    "NOT NULL", "販売数量合計"),
    ("gold_store_ranking", "transaction_count",   "LongType",    "NOT NULL", "取引件数"),

    ("gold_unregistered_master_report", "transaction_id",        "StringType",  "NOT NULL", "取引ID"),
    ("gold_unregistered_master_report", "issue_type",            "StringType",  "NOT NULL", "未登録の種別（store_id未登録／product_id未登録／両方）"),
    ("gold_unregistered_master_report", "store_id",              "StringType",  "NULL",     "取引に記録された店舗ID（store_masterに存在しない値を含む）"),
    ("gold_unregistered_master_report", "is_store_registered",   "BooleanType", "NOT NULL", "store_masterに登録済みかどうか"),
    ("gold_unregistered_master_report", "product_id",            "StringType",  "NULL",     "取引に記録された商品ID（product_masterに存在しない値を含む）"),
    ("gold_unregistered_master_report", "is_product_registered", "BooleanType", "NOT NULL", "product_masterに登録済みかどうか"),
    ("gold_unregistered_master_report", "customer_id",           "StringType",  "NULL",     "顧客ID（非会員購入時はnull）"),
    ("gold_unregistered_master_report", "transaction_datetime",  "StringType",  "NULL",     "取引日時（原文のまま保持。フォーマット不整合の確認用）"),
    ("gold_unregistered_master_report", "quantity",              "IntegerType", "NULL",     "購入数量"),
    ("gold_unregistered_master_report", "unit_price",            "DoubleType",  "NULL",     "単価（円）"),
    ("gold_unregistered_master_report", "discount_amount",       "DoubleType",  "NULL",     "割引額（円）。discount null課題によりnullを含む"),
    ("gold_unregistered_master_report", "sales_amount",          "DoubleType",  "NULL",     "売上金額（円）"),
]
column_schema = StructType([
    StructField("table_name",  StringType()),
    StructField("column_name", StringType()),
    StructField("data_type",   StringType()),
    StructField("nullable",    StringType()),
    StructField("description", StringType()),
])
df_gold_column_design = spark.createDataFrame(gold_column_design, schema=column_schema)

print("=" * 80)
print("Output 1-b: Gold layer カラム定義（データ型・nullable・説明）")
print("=" * 80)
df_gold_column_design.show(100, truncate=False)


# ================================================================
# Output 2: Gold layer 表定義（空表）の保存
#   ※ サンプルデータからの集計・クレンジングは行わず、設計通りの空表を保存するのみ
#
#   注：DataFrame（StructTypeでnullable=False指定）を saveAsTable() で保存する方式は
#      NOT NULL制約がテーブル定義に反映されない（全列nullable=trueになる）ため、
#      CREATE TABLE ... USING DELTA のDDLで直接テーブルを作成する方式を採用する。
# ================================================================

spark.sql("CREATE DATABASE IF NOT EXISTS gold")
spark.sql("USE gold")
print("データベース 'gold' を選択しました")


# ──────────────────────────────────────────────
# 1. gold_daily_store_sales（日別店舗別売上）
# ──────────────────────────────────────────────

spark.sql("""
    CREATE OR REPLACE TABLE gold.gold_daily_store_sales (
        sales_date          DATE   NOT NULL,
        store_id             STRING NOT NULL,
        store_name           STRING NOT NULL,
        region               STRING NOT NULL,
        transaction_count    BIGINT NOT NULL,
        total_quantity       BIGINT NOT NULL,
        total_sales_amount   DOUBLE NOT NULL
    )
    USING DELTA
""")
print("gold_daily_store_sales（空表）を保存しました")


# ──────────────────────────────────────────────
# 2. gold_category_sales（商品カテゴリ別売上）
# ──────────────────────────────────────────────

spark.sql("""
    CREATE OR REPLACE TABLE gold.gold_category_sales (
        category             STRING NOT NULL,
        product_count        BIGINT NOT NULL,
        transaction_count    BIGINT NOT NULL,
        total_quantity       BIGINT NOT NULL,
        total_sales_amount   DOUBLE NOT NULL
    )
    USING DELTA
""")
print("gold_category_sales（空表）を保存しました")


# ──────────────────────────────────────────────
# 3. gold_store_ranking（店舗ランキング）
# ──────────────────────────────────────────────

spark.sql("""
    CREATE OR REPLACE TABLE gold.gold_store_ranking (
        sales_rank           INT    NOT NULL,
        store_id             STRING NOT NULL,
        store_name           STRING NOT NULL,
        region               STRING NOT NULL,
        store_type           STRING NOT NULL,
        total_sales_amount   DOUBLE NOT NULL,
        total_quantity       BIGINT NOT NULL,
        transaction_count    BIGINT NOT NULL
    )
    USING DELTA
""")
print("gold_store_ranking（空表）を保存しました")


# ──────────────────────────────────────────────
# 4. gold_unregistered_master_report（マスター未登録レポート）
# ──────────────────────────────────────────────

spark.sql("""
    CREATE OR REPLACE TABLE gold.gold_unregistered_master_report (
        transaction_id          STRING  NOT NULL,
        issue_type              STRING  NOT NULL,
        store_id                STRING,
        is_store_registered     BOOLEAN NOT NULL,
        product_id               STRING,
        is_product_registered   BOOLEAN NOT NULL,
        customer_id              STRING,
        transaction_datetime     STRING,
        quantity                 INT,
        unit_price               DOUBLE,
        discount_amount          DOUBLE,
        sales_amount             DOUBLE
    )
    USING DELTA
""")
print("gold_unregistered_master_report（空表）を保存しました")


# ================================================================
# 保存結果を確認するためのコード
# ================================================================

GOLD_TABLES = [
    "gold_daily_store_sales",
    "gold_category_sales",
    "gold_store_ranking",
    "gold_unregistered_master_report",
]

print("\n" + "=" * 80)
print("=== 保存結果の確認（スキーマ・件数） ===")
print("=" * 80)

for table_name in GOLD_TABLES:
    full_name = f"gold.{table_name}"
    print(f"\n--- {full_name} ---")
    spark.table(full_name).printSchema()
    row_count = spark.table(full_name).count()
    print(f"件数: {row_count} 件（空表のため0件が正しい状態）")

print("\n=== Gold layer 表定義（空表）の保存完了 ===")
