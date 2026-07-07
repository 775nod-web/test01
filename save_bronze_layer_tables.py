# Databricks ノートブック用
# sample スキーマに保存済みのサンプルデータ（POS/商品マスター/店舗マスター/会員マスター）を、
# 列の値を一切変更・加工せず、取り込みメタデータ列のみを追加してBronzeレイヤーに保存する
#
# 前提：sample.sample_pos_transactions 等が存在すること
#       （generate_retail_sample_data.py と save_sample_retail_tables.py を実行済みであること）
# 動作確認環境：Databricks Free Edition（Unity Catalog）
#
# Bronzeレイヤーの原則：ソースの生データをそのまま保持し、
# 取り込み時刻・取り込み元システム・バッチIDなどの「取り込みメタデータ」列のみを付加する。
# 既存列の値の変換・欠損補完・型変換・フィルタリングは行わない。

from pyspark.sql import functions as F
from datetime import datetime
import uuid

CATALOG = spark.catalog.currentCatalog()
SAMPLE_SCHEMA = f"{CATALOG}.sample"
BRONZE_SCHEMA = f"{CATALOG}.bronze"

# ──────────────────────────────────────────────
# 0. Bronzeスキーマの作成（存在しない場合のみ）
# ──────────────────────────────────────────────

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {BRONZE_SCHEMA}")
spark.sql(f"USE {BRONZE_SCHEMA}")
print(f"スキーマ '{BRONZE_SCHEMA}' を使用します")

# 同一バッチ内のすべてのテーブルで共通の取り込みメタデータにする
# （current_timestamp()を都度呼ぶとテーブルごとに時刻がずれるため、Python側で1回だけ値を確定する）
INGESTED_AT_VALUE = datetime.now()
BATCH_ID = str(uuid.uuid4())

# (source_table, target_table, source_system) の対応
SOURCE_TO_BRONZE = [
    ("sample_pos_transactions", "bronze_pos_transactions", "POS"),
    ("sample_product_master",   "bronze_product_master",   "product_master_system"),
    ("sample_store_master",     "bronze_store_master",     "store_master_system"),
    ("sample_member_master",    "bronze_member_master",    "member_master_system"),
]


def ingest_to_bronze(source_table: str, target_table: str, source_system: str) -> int:
    """生データの列はそのままに、取り込みメタデータ列のみを付与してBronzeテーブルに保存する"""
    df_source = spark.table(f"{SAMPLE_SCHEMA}.{source_table}")

    df_bronze = (
        df_source
        .withColumn("_bronze_ingested_at", F.lit(INGESTED_AT_VALUE).cast("timestamp"))
        .withColumn("_bronze_source_system", F.lit(source_system))
        .withColumn("_bronze_batch_id", F.lit(BATCH_ID))
    )

    full_target = f"{BRONZE_SCHEMA}.{target_table}"
    (
        df_bronze.write
        .format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable(full_target)
    )
    count = spark.table(full_target).count()
    print(f"{full_target} 保存完了: {count:,} 件（source_system={source_system}）")
    return count


# ──────────────────────────────────────────────
# 1. 各表をBronzeレイヤーへ取り込み
# ──────────────────────────────────────────────

bronze_counts = {}
for source_table, target_table, source_system in SOURCE_TO_BRONZE:
    bronze_counts[target_table] = ingest_to_bronze(source_table, target_table, source_system)


# ──────────────────────────────────────────────
# 2. 保存結果サマリーの表示
# ──────────────────────────────────────────────

print("\n" + "=" * 40)
print(f"=== {BRONZE_SCHEMA} 保存完了サマリー ===")
print("=" * 40)
print(f"  バッチID    : {BATCH_ID}")
print(f"  取り込み時刻: {INGESTED_AT_VALUE}")
for target_table, count in bronze_counts.items():
    print(f"  {target_table:<28}: {count:>6,} 件")
print("=" * 40)
