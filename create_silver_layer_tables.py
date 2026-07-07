"""
Silver レイヤー作成スクリプト（Databricks Free Edition Notebook 用）

前提: save_bronze_layer_tables.py を実行済みで、
      bronze.customer_master / bronze.contract_data / bronze.support_tickets
      が Delta テーブルとして保存されていること。

Bronzeレイヤーの生データに対し、Knowledge baseで定義された品質課題を
検出・改善（標準化／重複排除／異常値の無効化）した上で、
silver スキーマ（無ければ作成）に Delta テーブルとして保存する。

customer_master / contract_data はBronze時点で品質課題を含まない設計のため、
メタデータの整形のみを行いそのまま複製する。品質改善の主対象は support_tickets。

support_tickets に対する品質改善の内容（Knowledge baseの品質課題に対応）:
  1. 顧客ID不一致・欠損   : customer_masterに存在するか判定し is_customer_id_valid
                             フラグを付与（レコードは削除せず保持し、Gold層で
                             customer_masterとの内部結合により自然に除外できるようにする）
  2. チケットID重複       : 同一ticket_idは1件に重複排除（複数存在した事実は
                             data_quality_flagsに記録して残す）
  3. 優先度の表記揺れ     : 正規値 Low/Medium/High に標準化
  4. ステータスの表記揺れ : 正規値 Open/In Progress/Resolved/Closed に標準化
  5. カテゴリ欠損         : 欠損はねつ造せずNULLのまま保持（フラグのみ記録）
  6. センチメント欠損     : 同上
  7. 解決時間の欠損/異常値: 解決済みなのに欠損 → フラグのみ記録（値は変更しない）
                             720時間(30日)を超える異常値 → 信頼できない値として
                             NULLに無効化（Gold層の平均解決時間計算への悪影響を防止）
  8. 作成日時のフォーマット揺れ: 複数フォーマットを試行しTIMESTAMP型に標準化

いずれの品質課題も、検出結果を data_quality_flags 列（配列）に記録することで、
後工程（Gold層のデータ品質サマリ）でも参照できるようにしている。
"""

from pyspark.sql import functions as F
from pyspark.sql.window import Window

# ──────────────────────────────────────────────
# 0. 保存先スキーマの作成（無ければ作成）
# ──────────────────────────────────────────────

spark.sql("CREATE SCHEMA IF NOT EXISTS silver")
print("スキーマ 'silver' を選択しました（存在しない場合は作成済み）")


# ──────────────────────────────────────────────
# 1. 顧客マスター・契約データ（品質課題なし → メタデータ整形のみ）
# ──────────────────────────────────────────────

def promote_clean_table_to_silver(bronze_table: str, silver_table: str) -> None:
    """Bronzeで品質課題を持たないテーブルを、メタデータのみ整形してSilverに複製する"""
    df_silver = (
        spark.table(bronze_table)
        .withColumnRenamed("ingested_at", "bronze_ingested_at")
        .withColumn("silver_processed_at", F.current_timestamp())
    )
    (
        df_silver.write.format("delta").mode("overwrite").option("overwriteSchema", "true")
        .saveAsTable(silver_table)
    )
    print(f"{silver_table} 保存完了: {spark.table(silver_table).count()} 件")


promote_clean_table_to_silver("bronze.customer_master", "silver.customer_master")
promote_clean_table_to_silver("bronze.contract_data", "silver.contract_data")


# ──────────────────────────────────────────────
# 2. サポートチケット（品質改善のメイン対象）
# ──────────────────────────────────────────────

VALID_CUSTOMER_IDS = [r.customer_id for r in spark.table("silver.customer_master")
                      .select("customer_id").collect()]

PRIORITIES_CANONICAL = ["Low", "Medium", "High"]
STATUSES_CANONICAL = ["Open", "In Progress", "Resolved", "Closed"]
RESOLVED_LIKE_LOWER = ["resolved", "closed", "close"]
RESOLUTION_HOURS_MAX = 720.0  # 30日。これを超える値は異常値とみなす
CANONICAL_CREATED_AT_REGEX = r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$"

# 表記揺れの正規化マッピング（キーは小文字で判定）
PRIORITY_MAPPING = {
    "low": "Low", "medium": "Medium", "high": "High",
    "urget": "High", "urgent": "High",
}
STATUS_MAPPING = {
    "open": "Open", "in progress": "In Progress", "inprogress": "In Progress",
    "resolved": "Resolved", "closed": "Closed", "close": "Closed",
}


def build_mapping_column(mapping: dict):
    """Python辞書からSparkのMAP列（定数）を作る（UDFを使わずelement_atで参照する）"""
    items = []
    for key, value in mapping.items():
        items.extend([F.lit(key), F.lit(value)])
    return F.create_map(*items)


priority_map_col = build_mapping_column(PRIORITY_MAPPING)
status_map_col = build_mapping_column(STATUS_MAPPING)

df_bronze_tickets = spark.table("bronze.support_tickets")

# --- (a) 品質課題の検出（変換前の生値に対して判定） ---
dup_window = Window.partitionBy("ticket_id")

df_checked = (
    df_bronze_tickets
    .withColumn("_customer_null", F.col("customer_id").isNull())
    .withColumn(
        "_customer_unmatched",
        F.col("customer_id").isNotNull() & (~F.col("customer_id").isin(VALID_CUSTOMER_IDS)),
    )
    .withColumn("_is_duplicate_id", F.count("*").over(dup_window) > 1)
    .withColumn(
        "_priority_variant",
        F.col("priority").isNotNull() & (~F.col("priority").isin(PRIORITIES_CANONICAL)),
    )
    .withColumn(
        "_status_variant",
        F.col("status").isNotNull() & (~F.col("status").isin(STATUSES_CANONICAL)),
    )
    .withColumn(
        "_is_resolved_like",
        F.lower(F.col("status")).isin(RESOLVED_LIKE_LOWER),
    )
    .withColumn(
        "_resolution_missing",
        F.col("_is_resolved_like") & F.col("resolution_hours").isNull(),
    )
    .withColumn(
        "_resolution_outlier",
        F.col("resolution_hours").isNotNull() & (F.col("resolution_hours") > RESOLUTION_HOURS_MAX),
    )
    .withColumn(
        "_created_at_variant",
        ~F.col("created_at").rlike(CANONICAL_CREATED_AT_REGEX),
    )
)

# --- (b) 検出結果を data_quality_flags 配列列に記録 ---
df_flagged = df_checked.withColumn(
    "data_quality_flags",
    F.filter(
        F.array(
            F.when(F.col("_customer_null"), F.lit("customer_id_null")),
            F.when(F.col("_customer_unmatched"), F.lit("customer_id_unmatched")),
            F.when(F.col("_is_duplicate_id"), F.lit("ticket_id_duplicate")),
            F.when(F.col("_priority_variant"), F.lit("priority_format_variant")),
            F.when(F.col("_status_variant"), F.lit("status_format_variant")),
            F.when(F.col("category").isNull(), F.lit("category_null")),
            F.when(F.col("sentiment").isNull(), F.lit("sentiment_null")),
            F.when(F.col("_resolution_missing"), F.lit("resolution_hours_missing")),
            F.when(F.col("_resolution_outlier"), F.lit("resolution_hours_outlier")),
            F.when(F.col("_created_at_variant"), F.lit("created_at_format_variant")),
        ),
        lambda x: x.isNotNull(),
    ),
)

# --- (c) 品質改善（標準化・異常値の無効化・型変換） ---
df_cleaned = (
    df_flagged
    .withColumn(
        "priority",
        F.coalesce(F.element_at(priority_map_col, F.lower(F.col("priority"))), F.col("priority")),
    )
    .withColumn(
        "status",
        F.coalesce(F.element_at(status_map_col, F.lower(F.col("status"))), F.col("status")),
    )
    .withColumn(
        "resolution_hours",
        F.when(F.col("_resolution_outlier"), F.lit(None).cast("double"))
         .otherwise(F.col("resolution_hours")),
    )
    .withColumn(
        "created_at",
        # try_to_timestamp はパース失敗時に例外を出さずNULLを返すため、
        # ANSIモード(Databricks/Spark既定)でも複数フォーマットを安全に試行できる
        F.coalesce(
            F.try_to_timestamp("created_at", F.lit("yyyy-MM-dd HH:mm:ss")),      # 正規フォーマット
            F.try_to_timestamp("created_at", F.lit("yyyy-MM-dd'T'HH:mm:ss'Z'")),  # ISO8601
            F.try_to_timestamp("created_at", F.lit("dd-MM-yyyy HH:mm:ss")),      # DD-MM-YYYY
            F.try_to_timestamp("created_at", F.lit("yyyy/MM/dd HH:mm")),        # "/" 区切り・秒なし
        ),
    )
    .withColumn(
        "is_customer_id_valid",
        F.col("customer_id").isNotNull() & F.col("customer_id").isin(VALID_CUSTOMER_IDS),
    )
)

# --- (d) チケットID重複排除（1 ticket_id につき1レコードへ） ---
dedup_order_window = Window.partitionBy("ticket_id").orderBy(F.monotonically_increasing_id())
df_deduped = (
    df_cleaned
    .withColumn("_row_num", F.row_number().over(dedup_order_window))
    .filter(F.col("_row_num") == 1)
    .drop("_row_num")
)

# --- (e) メタデータの整形・不要な内部フラグ列の削除 ---
df_silver_support_tickets = (
    df_deduped
    .withColumnRenamed("ingested_at", "bronze_ingested_at")
    .withColumn("silver_processed_at", F.current_timestamp())
    .select(
        "ticket_id", "customer_id", "is_customer_id_valid", "created_at",
        "priority", "status", "category", "sentiment", "resolution_hours",
        "subject", "data_quality_flags",
        "source_system", "bronze_ingested_at", "silver_processed_at",
    )
)

(
    df_silver_support_tickets
    .write.format("delta").mode("overwrite").option("overwriteSchema", "true")
    .saveAsTable("silver.support_tickets")
)

print(f"silver.support_tickets 保存完了: {spark.table('silver.support_tickets').count()} 件"
      f"（Bronze {df_bronze_tickets.count()} 件からticket_id重複排除後）")

print("\n=== silver スキーマへの保存が完了しました ===")
print("  silver.customer_master")
print("  silver.contract_data")
print("  silver.support_tickets")
