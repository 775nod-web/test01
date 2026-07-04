"""
小売メダリオンアーキテクチャ Bronze layer 構築スクリプト（Databricks Free Edition想定）
==================================================================

■ Bronze layerの目的
    監査・障害時のリカバリのため、データソースの生データをそのまま保管する。
    サンプルデータの値そのものは一切変更せず、取り込み管理のために
    「データソース名」「取り込み日時」の2列のみを追加で付与する。

■ 前提（sample layer）
    sample.store_master / sample.product_master / sample.customer_master / sample.pos_sales
    が Delta テーブルとして保存済みであること。
    存在しない場合は本スクリプトが generate_retail_medallion_sample_data.py と
    save_retail_sample_delta_tables.py を自動実行して補完する。

■ 今回作成する Bronze layer 表（sample layerの4表にそのまま対応）
    1. bronze_store_master     ← sample.store_master
    2. bronze_product_master   ← sample.product_master
    3. bronze_customer_master  ← sample.customer_master
    4. bronze_pos_sales        ← sample.pos_sales

Databricks ノートブックでは spark はクラスターから自動注入されるため
SparkSession.builder は呼ばない。
"""

from pyspark.sql import functions as F


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
# Output 1: サンプルデータを変更せずにBronze layerの表として保存するコード
# ================================================================

spark.sql("CREATE DATABASE IF NOT EXISTS bronze")
spark.sql("USE bronze")
print("データベース 'bronze' を選択しました")


def add_ingestion_metadata(df, source_system: str):
    """サンプルデータの列・値は一切変更せず、取り込み管理用の2列のみを追加する
    ・source_system : データソース名（取り込み元システムの識別子）
    ・ingested_at    : 取り込み日時（本スクリプト実行時のタイムスタンプ）
    """
    return (
        df
        .withColumn("source_system", F.lit(source_system))
        .withColumn("ingested_at", F.current_timestamp())
    )


# ──────────────────────────────────────────────
# 1. 店舗マスター → bronze.bronze_store_master
# ──────────────────────────────────────────────

df_bronze_store_master = add_ingestion_metadata(
    spark.table("sample.store_master"), "STORE_MASTER_SYSTEM"
)
(
    df_bronze_store_master.write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("bronze.bronze_store_master")
)
print("bronze_store_master 保存完了")


# ──────────────────────────────────────────────
# 2. 商品マスター → bronze.bronze_product_master
# ──────────────────────────────────────────────

df_bronze_product_master = add_ingestion_metadata(
    spark.table("sample.product_master"), "PRODUCT_MASTER_SYSTEM"
)
(
    df_bronze_product_master.write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("bronze.bronze_product_master")
)
print("bronze_product_master 保存完了")


# ──────────────────────────────────────────────
# 3. 顧客/会員データ → bronze.bronze_customer_master
# ──────────────────────────────────────────────

df_bronze_customer_master = add_ingestion_metadata(
    spark.table("sample.customer_master"), "CRM_SYSTEM"
)
(
    df_bronze_customer_master.write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("bronze.bronze_customer_master")
)
print("bronze_customer_master 保存完了")


# ──────────────────────────────────────────────
# 4. POS売上イベント → bronze.bronze_pos_sales
# ──────────────────────────────────────────────

df_bronze_pos_sales = add_ingestion_metadata(
    spark.table("sample.pos_sales"), "POS_SYSTEM"
)
(
    df_bronze_pos_sales.write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("bronze.bronze_pos_sales")
)
print("bronze_pos_sales 保存完了")


# ================================================================
# Output 2: Bronze layerとして保存した表のデータ・件数を表示するコード
# ================================================================

BRONZE_TABLES = [
    "bronze_store_master",
    "bronze_product_master",
    "bronze_customer_master",
    "bronze_pos_sales",
]

print("\n" + "=" * 80)
print("=== Bronze layer 各表のデータ（先頭5件） ===")
print("=" * 80)

for table_name in BRONZE_TABLES:
    full_name = f"bronze.{table_name}"
    print(f"\n--- {full_name} ---")
    spark.table(full_name).show(5, truncate=False)

print("\n" + "=" * 80)
print("=== Bronze layer 各表の件数 ===")
print("=" * 80)

for table_name in BRONZE_TABLES:
    full_name = f"bronze.{table_name}"
    sample_name = f"sample.{table_name.replace('bronze_', '')}"
    bronze_count = spark.table(full_name).count()
    sample_count = spark.table(sample_name).count()
    match_mark = "OK" if bronze_count == sample_count else "MISMATCH"
    print(f"  {full_name:<28} : {bronze_count:>4,} 件 "
          f"（sample側 {sample_count:>4,} 件との一致: {match_mark}）")

print("\n=== Bronze layer 保存・確認完了 ===")
