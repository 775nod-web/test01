"""
Silver layer 保存スクリプト
- bronze スキーマの3表（customers / accounts / transactions）を読み込み、
  Knowledge baseで定義された品質課題に対応するクレンジング・標準化・検証を行い、
  Silver layer のテーブルとして保存する

方針:
  - 重複（ETL起因の技術的ノイズ）のみ実際に除外する
  - それ以外の品質課題（マスタ不一致・金額異常・カテゴリ不明 等）は
    不正検知においてそれ自体がリスクシグナルになり得るため「除外せず、
    正規化した値 + 品質フラグを付与して保持」する
      -> Gold layer 側で「疑わしい取引」の判定材料として利用できるようにする

保存先スキーマ: silver（存在しない場合は自動作成）
  - silver.customers
  - silver.accounts
  - silver.transactions

前提: bronze.customers / bronze.accounts / bronze.transactions が
      作成済みであること（save_bronze_layer_tables.py を先に実行）
動作確認環境: Databricks Free Edition
"""

from pyspark.sql import functions as F
from pyspark.sql.window import Window

# Databricks ノートブックでは spark はクラスターから自動注入される


# ──────────────────────────────────────────────
# 0. 保存先スキーマ（silver）の作成
# ──────────────────────────────────────────────

spark.sql("CREATE SCHEMA IF NOT EXISTS silver")
print("スキーマ 'silver' を作成/選択しました")


# ──────────────────────────────────────────────
# 1. 顧客マスタ（silver.customers）
#    品質課題は含まれていないためほぼそのまま採用し、
#    Bronzeの取り込みメタデータ列を Silver処理時刻に置き換える
# ──────────────────────────────────────────────

df_customers_bronze = spark.table("bronze.customers")

df_customers_silver = df_customers_bronze.select(
    "customer_id",
    "customer_type",
    "birth_date",
    "risk_category",
    "residence_country",
    "registration_date",
).withColumn("silver_processed_at", F.current_timestamp())


# ──────────────────────────────────────────────
# 2. 口座マスタ（silver.accounts）
#    品質課題は含まれていないためほぼそのまま採用
# ──────────────────────────────────────────────

df_accounts_bronze = spark.table("bronze.accounts")

df_accounts_silver = df_accounts_bronze.select(
    "account_id",
    "customer_id",
    "account_type",
    "open_date",
    "account_status",
).withColumn("silver_processed_at", F.current_timestamp())


# ──────────────────────────────────────────────
# 3. 取引イベント（silver.transactions）
#    Knowledge baseの品質課題に対応したクレンジング・標準化・検証
# ──────────────────────────────────────────────

df_transactions_bronze = spark.table("bronze.transactions")
bronze_count = df_transactions_bronze.count()

# --- 3-1. transaction_id 重複の除去 ---
# 重複はETL起因の技術的ノイズであり業務的な意味を持たないため、1件目のみ残す
w_dedup = Window.partitionBy("transaction_id").orderBy(
    F.col("ingested_at").asc(), F.monotonically_increasing_id().asc()
)
df_dedup = (
    df_transactions_bronze
    .withColumn("_rn", F.row_number().over(w_dedup))
    .filter(F.col("_rn") == 1)
    .drop("_rn")
)
duplicate_removed_count = bronze_count - df_dedup.count()

# --- 3-2. タイムスタンプの標準化 ---
# 複数フォーマットを順に試行し、パースできた最初の結果を採用する
# （ANSIモードでも例外を送出しない try_to_timestamp を使用）
ts_col = F.col("transaction_ts")
parsed_iso = F.try_to_timestamp(ts_col, F.lit("yyyy-MM-dd'T'HH:mm:ssXXX"))     # 例: 2026-07-01T09:15:00+09:00
parsed_space = F.try_to_timestamp(ts_col, F.lit("yyyy-MM-dd HH:mm:ss"))       # 例: 2026-07-02 21:00:00
parsed_slash = F.try_to_timestamp(ts_col, F.lit("yyyy/MM/dd HH:mm:ss"))       # 例: 2026/07/03 07:45:00
parsed_mmdd = F.try_to_timestamp(ts_col, F.lit("MM-dd-yyyy HH:mm:ss"))        # 例: 07-04-2026 13:10:00
parsed_epoch = F.when(
    ts_col.rlike(r"^\d{9,10}$"), F.timestamp_seconds(ts_col.cast("long"))     # 例: 1751603400 (UNIX秒)
)

df_ts = (
    df_dedup
    .withColumn(
        "transaction_timestamp",
        F.coalesce(parsed_iso, parsed_space, parsed_slash, parsed_mmdd, parsed_epoch),
    )
    .withColumn("is_timestamp_valid", F.col("transaction_timestamp").isNotNull())
)

# --- 3-3. カントリーコードの標準化 ---
# JP / Japan / JPN / jp / " JP " など日本を表す表記揺れを "JP" に正規化
country_upper_trim = F.upper(F.trim(F.col("country_code")))
df_country = df_ts.withColumn(
    "country_code_clean",
    F.when(country_upper_trim.isin("JP", "JAPAN", "JPN"), F.lit("JP")).otherwise(country_upper_trim),
)

# --- 3-4. 加盟店カテゴリの標準化 ---
# 大文字小文字等の表記揺れは正規カテゴリへマッピング。
# 綴りが異なる等マッピング不能な値は誤補正を避けるためNULLのまま残し、is_category_validで検知可能にする
VALID_CATEGORIES = ["Grocery", "Restaurant", "Electronics", "Travel", "Utilities", "Entertainment"]
category_map_expr = F.create_map(
    [F.lit(x) for pair in [(c.upper(), c) for c in VALID_CATEGORIES] for x in pair]
)
category_key = F.upper(F.trim(F.col("merchant_category")))
df_category = (
    df_country
    .withColumn("merchant_category_clean", category_map_expr[category_key])
    .withColumn(
        "is_category_valid",
        F.when(
            # ATM/出金取引はカテゴリがNULLでも業務上正当
            F.col("transaction_type").isin("atm", "withdrawal") & F.col("merchant_category").isNull(),
            F.lit(True),
        ).otherwise(F.col("merchant_category_clean").isNotNull()),
    )
)

# --- 3-5. 金額異常フラグ ---
# 0円・マイナスの取引は削除せず、フラグを立てて保持する（不正調査上の重要シグナルになり得るため）
df_amount = df_category.withColumn("is_amount_valid", F.col("amount") > 0)

# --- 3-6. マスタ参照整合性フラグ ---
# customer_id / account_id がマスタに存在するかを検証（除外はせずフラグ付けのみ）
df_ref = (
    df_amount
    .join(
        df_customers_silver.select("customer_id").withColumn("is_customer_valid", F.lit(True)),
        on="customer_id", how="left",
    )
    .join(
        df_accounts_silver.select("account_id").withColumn("is_account_valid", F.lit(True)),
        on="account_id", how="left",
    )
    .fillna({"is_customer_valid": False, "is_account_valid": False})
)

# --- 3-7. 同一顧客の短時間複数取引（バーストパターン）特徴量 ---
# 標準化済みタイムスタンプを用いて、同一顧客の直前取引との経過秒数を算出
w_customer = Window.partitionBy("customer_id").orderBy("transaction_timestamp")
df_burst = (
    df_ref
    .withColumn("_prev_ts", F.lag("transaction_timestamp").over(w_customer))
    .withColumn(
        "seconds_since_prev_transaction",
        F.when(
            F.col("_prev_ts").isNotNull(),
            F.col("transaction_timestamp").cast("long") - F.col("_prev_ts").cast("long"),
        ),
    )
    .withColumn(
        "is_rapid_succession",
        F.col("seconds_since_prev_transaction").isNotNull()
        & (F.col("seconds_since_prev_transaction") <= 900),
    )
    .drop("_prev_ts")
)

# --- 3-8. 最終的な列構成の確定 ---
df_transactions_silver = (
    df_burst.select(
        "transaction_id",
        "customer_id",
        "account_id",
        "transaction_timestamp",
        "is_timestamp_valid",
        "amount",
        "is_amount_valid",
        "transaction_type",
        F.col("country_code").alias("country_code_raw"),
        "country_code_clean",
        F.col("merchant_category").alias("merchant_category_raw"),
        "merchant_category_clean",
        "is_category_valid",
        "fraud_label",
        "is_customer_valid",
        "is_account_valid",
        "seconds_since_prev_transaction",
        "is_rapid_succession",
        "source_system",
    )
    .withColumnRenamed("country_code_clean", "country_code")
    .withColumnRenamed("merchant_category_clean", "merchant_category")
    .withColumn("silver_processed_at", F.current_timestamp())
)


# ──────────────────────────────────────────────
# 4. Delta テーブルとして silver スキーマへ保存
# ──────────────────────────────────────────────

(
    df_customers_silver
    .write.format("delta").mode("overwrite").option("overwriteSchema", "true")
    .saveAsTable("silver.customers")
)

(
    df_accounts_silver
    .write.format("delta").mode("overwrite").option("overwriteSchema", "true")
    .saveAsTable("silver.accounts")
)

(
    df_transactions_silver
    .write.format("delta").mode("overwrite").option("overwriteSchema", "true")
    .saveAsTable("silver.transactions")
)


# ──────────────────────────────────────────────
# 5. 保存結果サマリーの表示
# ──────────────────────────────────────────────

print("\n" + "=" * 60)
print("=== Silver layer 保存完了 ===")
print("=" * 60)
print(f"  bronze.transactions 件数        : {bronze_count:>4,} 件")
print(f"  重複除去件数                     : {duplicate_removed_count:>4,} 件")
print(f"  silver.customers    : {spark.table('silver.customers').count():>4,} 件")
print(f"  silver.accounts     : {spark.table('silver.accounts').count():>4,} 件")
print(f"  silver.transactions : {spark.table('silver.transactions').count():>4,} 件")
print("=" * 60)
