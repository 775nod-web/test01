"""
小売メダリオンアーキテクチャ Gold layer 構築スクリプト（Databricks Free Edition想定）
==================================================================

■ ビジネス目的
    店舗・商品別の売上を可視化し、売上低下や人気商品の傾向を早期に把握する

■ 想定利用者
    本社営業管理 / 店長 / 商品企画 / データサイエンスチーム

■ 前提（Bronze/Sample layer）
    sample.store_master / sample.product_master / sample.customer_master / sample.pos_sales
    が Delta テーブルとして保存済みであること。
    存在しない場合は本スクリプトが generate_retail_medallion_sample_data.py と
    save_retail_sample_delta_tables.py を自動実行して補完する。

■ 今回作成する Gold layer 表（Knowledge base記載の4表のみ）
    1. gold_daily_store_sales         … 日別店舗別売上
    2. gold_category_sales            … 商品カテゴリ別売上
    3. gold_store_ranking              … 店舗ランキング
    4. gold_unregistered_master_report … マスター未登録レポート

Databricks ノートブックでは spark はクラスターから自動注入されるため
SparkSession.builder は呼ばない。
"""

from pyspark.sql import functions as F
from pyspark.sql.window import Window
from pyspark.sql.types import StructType, StructField, StringType, IntegerType


# ──────────────────────────────────────────────
# 0. 依存データ（sampleスキーマの4表）の存在確認・自動生成
#    ※ Python変数ではなく永続化されたDeltaテーブルの有無で判定することで、
#      ノートブック／セッションが分かれていても正しく動作するようにする
# ──────────────────────────────────────────────

if not spark.catalog.tableExists("sample.pos_sales"):
    print("sampleスキーマのテーブルが存在しないため、サンプルデータの生成・保存を先に実行します。")
    with open("generate_retail_medallion_sample_data.py", encoding="utf-8") as f:
        exec(f.read(), globals())
    with open("save_retail_sample_delta_tables.py", encoding="utf-8") as f:
        exec(f.read(), globals())


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
# Output 2: Gold layer 構築・保存コード
# ================================================================

spark.sql("CREATE DATABASE IF NOT EXISTS gold")
spark.sql("USE gold")
print("データベース 'gold' を選択しました")

df_sample_stores   = spark.table("sample.store_master")
df_sample_products = spark.table("sample.product_master")
df_sample_pos      = spark.table("sample.pos_sales")

# ──────────────────────────────────────────────
# 2-0. 共通クレンジング
#      ・重複transactionの除去（transaction_id単位でdrop duplicates）
#      ・store_id / product_id のマスター整合性フラグ付与
# ──────────────────────────────────────────────

df_pos_dedup = df_sample_pos.dropDuplicates(["transaction_id"])

valid_store_ids = [r.store_id for r in df_sample_stores.select("store_id").collect()]
valid_product_ids = [r.product_id for r in df_sample_products.select("product_id").collect()]

df_pos_flagged = (
    df_pos_dedup
    .withColumn("is_store_registered", F.col("store_id").isin(valid_store_ids))
    .withColumn("is_product_registered", F.col("product_id").isin(valid_product_ids))
)

# マスター整合済み（Gold集計3表の対象となる）取引データ
df_pos_valid = df_pos_flagged.filter(
    F.col("is_store_registered") & F.col("is_product_registered")
)

dedup_removed = df_sample_pos.count() - df_pos_dedup.count()
master_mismatch_removed = df_pos_dedup.count() - df_pos_valid.count()
print(f"重複transactionとして除去: {dedup_removed} 件")
print(f"マスター未登録として集計対象外: {master_mismatch_removed} 件")
print(f"Gold集計対象（クレンジング後）の有効取引数: {df_pos_valid.count()} 件")


# ──────────────────────────────────────────────
# 2-1. transaction_datetime の複数フォーマット対応パース
#      （時刻形式不一致の品質課題に対応。解析できない場合はnullとし、
#        日別集計（gold_daily_store_sales）からのみ除外する）
# ──────────────────────────────────────────────

DATETIME_FORMATS = [
    "yyyy-MM-dd HH:mm:ss",        # 標準フォーマット
    "yyyy/MM/dd HH:mm",
    "dd-MM-yyyy HH:mm:ss",
    "yyyyMMddHHmmss",
    "yyyy-MM-dd'T'HH:mm:ss'Z'",
    "MMM d, yyyy hh:mm a",
    "yyyy.MM.dd HH:mm",
    "d/M/yyyy HH:mm",
    "yyyy-MM-dd HH'時'mm'分'",
    "yyyyMMdd",
]


def parse_multi_format_timestamp(colname: str, formats: list):
    """複数の日時フォーマットを順に試し、最初に解析できた結果を採用する

    Databricksは既定でANSI SQLモードが有効なため、to_timestampはフォーマット
    不一致時に例外を送出してしまう。try_to_timestampを使うことで、解析に
    失敗した場合は例外にせずnullを返すようにする。
    """
    return F.coalesce(*[F.try_to_timestamp(F.col(colname), F.lit(fmt)) for fmt in formats])


df_pos_valid = (
    df_pos_valid
    .withColumn("parsed_datetime", parse_multi_format_timestamp("transaction_datetime", DATETIME_FORMATS))
    .withColumn("sales_date", F.to_date(F.col("parsed_datetime")))
)

unparseable_count = df_pos_valid.filter(F.col("sales_date").isNull()).count()
print(f"時刻形式を解析できず日付を特定できなかった取引: {unparseable_count} 件（gold_daily_store_salesのみ対象外）")


# ──────────────────────────────────────────────
# 2-2. gold_daily_store_sales（日別店舗別売上）
# ──────────────────────────────────────────────

df_gold_daily_store_sales = (
    df_pos_valid
    .filter(F.col("sales_date").isNotNull())
    .groupBy("sales_date", "store_id")
    .agg(
        F.count("transaction_id").alias("transaction_count"),
        F.sum("quantity").alias("total_quantity"),
        F.sum("sales_amount").alias("total_sales_amount"),
    )
    .join(df_sample_stores.select("store_id", "store_name", "region"), on="store_id", how="inner")
    .select("sales_date", "store_id", "store_name", "region",
            "transaction_count", "total_quantity", "total_sales_amount")
)

(
    df_gold_daily_store_sales.write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("gold.gold_daily_store_sales")
)
daily_store_sales_count = spark.table("gold.gold_daily_store_sales").count()
print(f"gold_daily_store_sales 保存完了: {daily_store_sales_count:,} 件")


# ──────────────────────────────────────────────
# 2-3. gold_category_sales（商品カテゴリ別売上）
# ──────────────────────────────────────────────

df_product_count_by_category = (
    df_sample_products.groupBy("category").agg(F.count("product_id").alias("product_count"))
)

df_gold_category_sales = (
    df_pos_valid
    .join(df_sample_products.select("product_id", "category"), on="product_id", how="inner")
    .groupBy("category")
    .agg(
        F.count("transaction_id").alias("transaction_count"),
        F.sum("quantity").alias("total_quantity"),
        F.sum("sales_amount").alias("total_sales_amount"),
    )
    .join(df_product_count_by_category, on="category", how="inner")
    .select("category", "product_count", "transaction_count", "total_quantity", "total_sales_amount")
)

(
    df_gold_category_sales.write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("gold.gold_category_sales")
)
category_sales_count = spark.table("gold.gold_category_sales").count()
print(f"gold_category_sales 保存完了: {category_sales_count:,} 件")


# ──────────────────────────────────────────────
# 2-4. gold_store_ranking（店舗ランキング）
# ──────────────────────────────────────────────

df_store_agg = (
    df_pos_valid
    .groupBy("store_id")
    .agg(
        F.count("transaction_id").alias("transaction_count"),
        F.sum("quantity").alias("total_quantity"),
        F.sum("sales_amount").alias("total_sales_amount"),
    )
)

ranking_window = Window.orderBy(F.col("total_sales_amount").desc())

df_gold_store_ranking = (
    df_store_agg
    .withColumn("sales_rank", F.rank().over(ranking_window).cast("int"))
    .join(
        df_sample_stores.select("store_id", "store_name", "region", "store_type"),
        on="store_id", how="inner",
    )
    .select("sales_rank", "store_id", "store_name", "region", "store_type",
            "total_sales_amount", "total_quantity", "transaction_count")
    .orderBy("sales_rank")
)

(
    df_gold_store_ranking.write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("gold.gold_store_ranking")
)
store_ranking_count = spark.table("gold.gold_store_ranking").count()
print(f"gold_store_ranking 保存完了: {store_ranking_count:,} 件")


# ──────────────────────────────────────────────
# 2-5. gold_unregistered_master_report（マスター未登録レポート）
#      ※ 重複transactionの除去のみ適用し、マスター整合性では絞り込まない
#        （このテーブル自体がマスター未登録取引を可視化するためのもの）
# ──────────────────────────────────────────────

df_gold_unregistered_master_report = (
    df_pos_flagged
    .filter(~F.col("is_store_registered") | ~F.col("is_product_registered"))
    .withColumn(
        "issue_type",
        F.when(~F.col("is_store_registered") & ~F.col("is_product_registered"),
               F.lit("store_id未登録,product_id未登録"))
         .when(~F.col("is_store_registered"), F.lit("store_id未登録"))
         .otherwise(F.lit("product_id未登録"))
    )
    .select("transaction_id", "issue_type", "store_id", "is_store_registered",
            "product_id", "is_product_registered", "customer_id",
            "transaction_datetime", "quantity", "unit_price",
            "discount_amount", "sales_amount")
)

(
    df_gold_unregistered_master_report.write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("gold.gold_unregistered_master_report")
)
unregistered_report_count = spark.table("gold.gold_unregistered_master_report").count()
print(f"gold_unregistered_master_report 保存完了: {unregistered_report_count:,} 件")


# ================================================================
# Output 2: 保存結果を確認するためのコード
# ================================================================

print("\n" + "=" * 80)
print("=== Gold layer 各表のサンプルデータ（先頭5件） ===")
print("=" * 80)

print("\n--- gold.gold_daily_store_sales ---")
spark.table("gold.gold_daily_store_sales").orderBy("sales_date", "store_id").show(5, truncate=False)

print("\n--- gold.gold_category_sales ---")
spark.table("gold.gold_category_sales").orderBy(F.col("total_sales_amount").desc()).show(5, truncate=False)

print("\n--- gold.gold_store_ranking ---")
spark.table("gold.gold_store_ranking").orderBy("sales_rank").show(5, truncate=False)

print("\n--- gold.gold_unregistered_master_report ---")
spark.table("gold.gold_unregistered_master_report").show(5, truncate=False)


print("\n" + "=" * 80)
print("=== Gold layer 各表の件数サマリー ===")
print("=" * 80)
print(f"  gold_daily_store_sales          : {daily_store_sales_count:>4,} 件")
print(f"  gold_category_sales             : {category_sales_count:>4,} 件")
print(f"  gold_store_ranking              : {store_ranking_count:>4,} 件")
print(f"  gold_unregistered_master_report : {unregistered_report_count:>4,} 件")


print("\n" + "=" * 80)
print("=== クレンジング内訳（sample.pos_sales → Gold集計対象） ===")
print("=" * 80)
print(f"  sample.pos_sales 全件           : {df_sample_pos.count():>4,} 件")
print(f"  うち 重複transaction除去        : {dedup_removed:>4,} 件")
print(f"  うち マスター未登録で集計対象外 : {master_mismatch_removed:>4,} 件（→ gold_unregistered_master_reportに計上）")
print(f"  うち 時刻形式解析不可（日別集計のみ対象外） : {unparseable_count:>4,} 件")
print(f"  Gold集計（カテゴリ別・店舗別）対象  : {df_pos_valid.count():>4,} 件")

print("\n=== Gold layer 保存・検証完了 ===")
