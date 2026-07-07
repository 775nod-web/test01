# Databricks ノートブック用
# Bronzeレイヤーの表を品質改善し、Silverレイヤーとして新しい表に保存する
#
# 前提：bronze.bronze_pos_transactions / bronze_product_master /
#       bronze_store_master / bronze_member_master が存在すること
#       （save_bronze_layer_tables.py を実行済みであること）
# 動作確認環境：Databricks Free Edition（Unity Catalog）
#
# 品質改善方針（Knowledge baseの8種類の品質課題に対応）
#   - transaction_idの重複            → 1件だけ残し、超過分は隔離表へ
#   - product_id / store_id のマスター不一致 → 有効なマスターに存在する行のみ採用、それ以外は隔離表へ
#   - quantityが0/負値                → 隔離表へ
#   - unit_priceがnull/負値           → 隔離表へ
#   - transaction_timestampの表記揺れ → JSTのTimestampTypeに正規化（5パターンを解析）
#   - customer_idがnull               → 除外はせず、非会員取引としてそのまま保持（情報として可視化）
#   - product categoryがnull          → 「未分類」で補完し、Gold集計で扱えるようにする

from pyspark.sql import functions as F
from pyspark.sql.window import Window
from datetime import datetime

CATALOG = spark.catalog.currentCatalog()
BRONZE_SCHEMA = f"{CATALOG}.bronze"
SILVER_SCHEMA = f"{CATALOG}.silver"

# ──────────────────────────────────────────────
# 0. Silverスキーマの作成（存在しない場合のみ）
# ──────────────────────────────────────────────

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {SILVER_SCHEMA}")
spark.sql(f"USE {SILVER_SCHEMA}")
print(f"スキーマ '{SILVER_SCHEMA}' を使用します")

PROCESSED_AT = datetime.now()

df_bronze_pos = spark.table(f"{BRONZE_SCHEMA}.bronze_pos_transactions")
df_bronze_product = spark.table(f"{BRONZE_SCHEMA}.bronze_product_master")
df_bronze_store = spark.table(f"{BRONZE_SCHEMA}.bronze_store_master")
df_bronze_member = spark.table(f"{BRONZE_SCHEMA}.bronze_member_master")


# ──────────────────────────────────────────────
# 1. 商品マスターの品質改善：categoryがnullの場合は「未分類」で補完
#    （商品削除ではなく補完することで、POS側の参照整合性とGoldのカテゴリ別集計を両立させる）
# ──────────────────────────────────────────────

df_silver_product = (
    df_bronze_product
    .withColumn("is_category_filled", F.col("category").isNull())
    .withColumn("category", F.coalesce(F.col("category"), F.lit("未分類")))
    .withColumn("_silver_processed_at", F.lit(PROCESSED_AT).cast("timestamp"))
    .select("product_id", "product_name", "category", "is_category_filled", "_silver_processed_at")
)

# ──────────────────────────────────────────────
# 2. 店舗マスター・会員マスターは品質課題を持たせていないためそのまま採用
# ──────────────────────────────────────────────

df_silver_store = (
    df_bronze_store
    .withColumn("_silver_processed_at", F.lit(PROCESSED_AT).cast("timestamp"))
    .select("store_id", "store_name", "region", "_silver_processed_at")
)

df_silver_member = (
    df_bronze_member
    .withColumn("_silver_processed_at", F.lit(PROCESSED_AT).cast("timestamp"))
    .select("customer_id", "customer_name", "registration_date", "_silver_processed_at")
)


# ──────────────────────────────────────────────
# 3. POSトランザクションの前処理
#    ・行を一意に識別するIDを付与する（重複排除の判定に使用）
#    ・transaction_timestamp（5パターン混在の文字列）をJSTのTimestampTypeに正規化
#    ・Gold集計で使う transaction_date / sales_amount を事前算出
# ──────────────────────────────────────────────

df_pos_base = df_bronze_pos.withColumn("_row_id", F.monotonically_increasing_id())

ts_col = F.col("transaction_timestamp")

transaction_ts = (
    F.when(ts_col.rlike(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$"),
           F.to_timestamp(ts_col, "yyyy-MM-dd HH:mm:ss"))
    .when(ts_col.rlike(r"^\d{4}/\d{2}/\d{2} \d{2}:\d{2}$"),
          F.to_timestamp(ts_col, "yyyy/MM/dd HH:mm"))
    .when(ts_col.rlike(r"^\d{2}-\d{2}-\d{4}T\d{2}:\d{2}:\d{2}\+\d{2}:\d{2}$"),
          F.to_timestamp(ts_col, "dd-MM-yyyy'T'HH:mm:ssXXX"))
    .when(ts_col.rlike(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"),
          F.from_utc_timestamp(
              F.to_timestamp(F.regexp_replace(ts_col, "Z$", ""), "yyyy-MM-dd'T'HH:mm:ss"),
              "Asia/Tokyo"))
    .when(ts_col.rlike(r"^\d{14}$"),
          F.to_timestamp(ts_col, "yyyyMMddHHmmss"))
    .otherwise(F.lit(None).cast("timestamp"))
)

df_pos_normalized = (
    df_pos_base
    .withColumn("transaction_ts", transaction_ts)
    .withColumn("transaction_date", F.to_date(F.col("transaction_ts")))
    .withColumn("sales_amount", F.col("quantity") * F.col("unit_price"))
)


# ──────────────────────────────────────────────
# 4. 有効/無効判定（マスター整合性・異常値・重複・タイムスタンプ解析可否）
#    customer_idのnullは非会員取引として許容し、無効判定には含めない
# ──────────────────────────────────────────────

valid_product_ids = [r.product_id for r in df_silver_product.select("product_id").collect()]
valid_store_ids = [r.store_id for r in df_silver_store.select("store_id").collect()]

is_product_valid = F.col("product_id").isin(valid_product_ids)
is_store_valid = F.col("store_id").isin(valid_store_ids)
is_quantity_valid = F.col("quantity") > 0
is_price_valid = F.col("unit_price").isNotNull() & (F.col("unit_price") >= 0)
is_timestamp_valid = F.col("transaction_ts").isNotNull()

# 重複transaction_idは _row_id 昇順で1件目のみ有効とし、超過分を無効とする
dup_window = Window.partitionBy("transaction_id").orderBy(F.col("_row_id"))
df_pos_ranked = df_pos_normalized.withColumn("_dup_rank", F.row_number().over(dup_window))
is_not_duplicate = F.col("_dup_rank") == 1

reject_reason_candidates = F.array(
    F.when(~is_product_valid, F.lit("product_id_not_in_master")),
    F.when(~is_store_valid, F.lit("store_id_not_in_master")),
    F.when(~is_quantity_valid, F.lit("quantity_invalid")),
    F.when(~is_price_valid, F.lit("unit_price_invalid")),
    F.when(~is_timestamp_valid, F.lit("timestamp_unparseable")),
    F.when(~is_not_duplicate, F.lit("duplicate_transaction_id")),
)

df_pos_flagged = (
    df_pos_ranked
    .withColumn("reject_reasons", F.filter(reject_reason_candidates, lambda x: x.isNotNull()))
    .withColumn("is_valid", F.size(F.col("reject_reasons")) == 0)
)


# ──────────────────────────────────────────────
# 4.5 判定結果をステージング表としていったん保存し、読み直す
#     Databricks Free Editionのサーバーレスコンピュートでは cache()/persist()
#     （PERSIST TABLE相当）が使えないため、代わりに一度Deltaへ書き込んでから
#     読み直すことで、有効/無効の判定結果を固定した状態で以降の分割処理を行う
# ──────────────────────────────────────────────

STAGING_TABLE = f"{SILVER_SCHEMA}.silver_pos_transactions_staging"

(
    df_pos_flagged
    .select(
        "transaction_id", "transaction_timestamp", "transaction_ts", "transaction_date",
        "store_id", "product_id", "customer_id",
        "quantity", "unit_price", "sales_amount",
        "reject_reasons", "is_valid",
    )
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(STAGING_TABLE)
)
df_pos_flagged_fixed = spark.table(STAGING_TABLE)


# ──────────────────────────────────────────────
# 5. 有効データ（silver_pos_transactions）と隔離データ（silver_pos_transactions_rejected）に分割
# ──────────────────────────────────────────────

df_silver_pos_valid = (
    df_pos_flagged_fixed
    .filter(F.col("is_valid"))
    .withColumn("_silver_processed_at", F.lit(PROCESSED_AT).cast("timestamp"))
    .select(
        "transaction_id", "transaction_ts", "transaction_date",
        "store_id", "product_id", "customer_id",
        "quantity", "unit_price", "sales_amount",
        "_silver_processed_at",
    )
)

df_silver_pos_rejected = (
    df_pos_flagged_fixed
    .filter(~F.col("is_valid"))
    .withColumn("_silver_processed_at", F.lit(PROCESSED_AT).cast("timestamp"))
    .select(
        "transaction_id", "transaction_timestamp", "transaction_ts",
        "store_id", "product_id", "customer_id",
        "quantity", "unit_price", "reject_reasons",
        "_silver_processed_at",
    )
)


# ──────────────────────────────────────────────
# 6. Delta保存
# ──────────────────────────────────────────────

def save_silver_table(df, table_name: str) -> int:
    full_name = f"{SILVER_SCHEMA}.{table_name}"
    (
        df.write
        .format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable(full_name)
    )
    count = spark.table(full_name).count()
    print(f"{full_name} 保存完了: {count:,} 件")
    return count


silver_counts = {
    "silver_product_master": save_silver_table(df_silver_product, "silver_product_master"),
    "silver_store_master": save_silver_table(df_silver_store, "silver_store_master"),
    "silver_member_master": save_silver_table(df_silver_member, "silver_member_master"),
    "silver_pos_transactions": save_silver_table(df_silver_pos_valid, "silver_pos_transactions"),
    "silver_pos_transactions_rejected": save_silver_table(df_silver_pos_rejected, "silver_pos_transactions_rejected"),
}

# ステージング表は最終成果物ではないため削除する
spark.sql(f"DROP TABLE IF EXISTS {STAGING_TABLE}")

print("\n" + "=" * 40)
print(f"=== {SILVER_SCHEMA} 保存完了サマリー ===")
print("=" * 40)
for table_name, count in silver_counts.items():
    print(f"  {table_name:<34}: {count:>6,} 件")
print("=" * 40)
