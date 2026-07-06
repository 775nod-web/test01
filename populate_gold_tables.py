# Databricks ノートブック用
# silverスキーマのクレンジング済みデータを集計し、goldスキーマの4表にデータを投入する
#
# 前提：
#   - create_gold_layer_tables.py を同セッションで実行済みであること
#     （gold.gold_daily_kpi / gold_at_risk_users / gold_data_quality_summary /
#       gold_user_ml_features がNOT NULL制約つきで作成済みであること）
#   - save_silver_tables.py を同セッションで実行済みであること
#     （silver.silver_users / silver_subscriptions / silver_user_events が存在すること）
# 動作確認環境：Databricks Free Edition
#
# 方針：
#   - is_valid_for_gold = true のレコードのみをGold集計の対象とする
#     （品質課題が残ったままのレコードをKPIに混入させない）
#   - サンプルデータは2023〜2024年の過去データのため、"今日"を意味する基準日として
#     current_date()（実行時の実日付）ではなく、データに含まれる最新イベント日時
#     （AS_OF_DATE）を使用する。これによりgold_at_risk_users/gold_user_ml_featuresの
#     「直近30日」等のウィンドウが意味を持つ（current_date()を使うと大幅に未来日付に
#     なり、直近ウィンドウが常に0件になってしまうため）。
#   - Gold表は先にDDLでNOT NULL制約つきで作成済みのため、書き込みは
#     overwriteSchemaオプションを使わず、既存スキーマを保持したまま行う。

from pyspark.sql import functions as F
from pyspark.sql.window import Window

SILVER_SCHEMA = "silver"
GOLD_SCHEMA = "gold"

spark.sql(f"USE {GOLD_SCHEMA}")

df_silver_users = spark.table(f"{SILVER_SCHEMA}.silver_users")
df_silver_subs = spark.table(f"{SILVER_SCHEMA}.silver_subscriptions").filter("is_valid_for_gold = true")
df_silver_events = spark.table(f"{SILVER_SCHEMA}.silver_user_events").filter("is_valid_for_gold = true")

# サブスクリプションにユーザーのcountry_codeを付与（is_valid_for_gold=trueはFK解決済みのためinner joinで問題ない）
df_subs_enriched = df_silver_subs.join(
    df_silver_users.select("user_id", "country_code"), on="user_id", how="inner"
)

# データに含まれる最新の日付を「基準日」とする
as_of_date_row = (
    df_subs_enriched.select(F.greatest(F.max("contract_start_date"), F.max("payment_date")).alias("d"))
    .union(df_silver_events.select(F.to_date(F.max("event_timestamp")).alias("d")))
    .agg(F.max("d").alias("as_of_date"))
    .collect()[0]
)
AS_OF_DATE = as_of_date_row["as_of_date"]
print(f"基準日(AS_OF_DATE): {AS_OF_DATE}")


# ──────────────────────────────────────────────
# 1. gold_daily_kpi
#    粒度: kpi_date × country_code × plan_type
# ──────────────────────────────────────────────

# (a) KPI算出対象の (kpi_date, country_code, plan_type) スパイン
#     その (country_code, plan_type) 自身に契約開始/終了/決済のいずれかが
#     発生した日だけを対象にする（他の国・プランの組み合わせと無条件にクロス結合すると、
#     その組み合わせ自身には無関係な日にまで行ができてしまい、Free Edition上でも
#     無駄に行数が膨らむため、各サブスクリプション自身の日付のみからスパインを作る）
kpi_spine = (
    df_subs_enriched.select("country_code", "plan_type", F.col("contract_start_date").alias("kpi_date"))
    .unionByName(df_subs_enriched.select("country_code", "plan_type", F.col("contract_end_date").alias("kpi_date")))
    .unionByName(df_subs_enriched.select("country_code", "plan_type", F.col("payment_date").alias("kpi_date")))
    .where(F.col("kpi_date").isNotNull())
    .distinct()
)

# (c) スパインと明細を (country_code, plan_type) で結合し、日付条件つきの条件集計を行う
kpi_joined = kpi_spine.join(df_subs_enriched, on=["country_code", "plan_type"], how="left")

daily_kpi_base = (
    kpi_joined
    .groupBy("kpi_date", "country_code", "plan_type")
    .agg(
        F.sum(F.when(F.col("contract_start_date") == F.col("kpi_date"), 1).otherwise(0)).alias("new_subscriptions_count"),
        F.sum(F.when(F.col("contract_end_date") == F.col("kpi_date"), 1).otherwise(0)).alias("churned_subscriptions_count"),
        F.sum(
            F.when(
                (F.col("contract_start_date") <= F.col("kpi_date"))
                & (F.col("contract_end_date").isNull() | (F.col("contract_end_date") > F.col("kpi_date"))),
                1,
            ).otherwise(0)
        ).alias("active_subscriptions_count"),
        F.sum(
            F.when((F.col("payment_date") == F.col("kpi_date")) & (F.col("payment_status") == "success"), F.col("amount"))
            .otherwise(0.0)
        ).alias("gross_revenue_amount"),
        F.sum(
            F.when((F.col("payment_date") == F.col("kpi_date")) & (F.col("payment_status") == "failed"), 1).otherwise(0)
        ).alias("failed_payment_count"),
    )
)

# (d) 転換率の分母: その国でまだどのプランにも転換していない「フリーユーザー数」（日次・国別）
first_paid_date_per_user = df_subs_enriched.groupBy("user_id").agg(F.min("contract_start_date").alias("first_paid_date"))
users_with_first_paid = df_silver_users.select("user_id", "country_code").join(
    first_paid_date_per_user, on="user_id", how="left"
)
country_day_spine = daily_kpi_base.select("country_code", "kpi_date").distinct()
free_users_by_day = (
    country_day_spine.join(users_with_first_paid, on="country_code")
    .groupBy("country_code", "kpi_date")
    .agg(
        F.sum(
            F.when(F.col("first_paid_date").isNull() | (F.col("first_paid_date") >= F.col("kpi_date")), 1).otherwise(0)
        ).alias("free_users_count")
    )
)

daily_kpi_with_free = daily_kpi_base.join(free_users_by_day, on=["country_code", "kpi_date"], how="left")

# (e) 解約率の分母: 同じ(country_code, plan_type)の「直前のKPI算出日」時点の有効契約数
#     ※ イベント発生日のみのスパインのため、厳密な暦日ベースの前日ではなく
#       「直前にイベントが発生した算出対象日」を前日相当として扱う簡易実装とする
window_spec = Window.partitionBy("country_code", "plan_type").orderBy("kpi_date")
daily_kpi_with_prev = daily_kpi_with_free.withColumn(
    "prev_active_subscriptions_count", F.lag("active_subscriptions_count").over(window_spec)
)

df_gold_daily_kpi = (
    daily_kpi_with_prev
    .withColumn(
        "conversion_rate",
        F.when(F.col("free_users_count") > 0, F.col("new_subscriptions_count") / F.col("free_users_count")),
    )
    .withColumn(
        "churn_rate",
        F.when(
            F.col("prev_active_subscriptions_count").isNotNull() & (F.col("prev_active_subscriptions_count") > 0),
            F.col("churned_subscriptions_count") / F.col("prev_active_subscriptions_count"),
        ),
    )
    .select(
        "kpi_date", "country_code", "plan_type",
        "new_subscriptions_count", "churned_subscriptions_count", "active_subscriptions_count",
        "gross_revenue_amount", "failed_payment_count", "conversion_rate", "churn_rate",
    )
)

df_gold_daily_kpi.write.format("delta").mode("overwrite").saveAsTable(f"{GOLD_SCHEMA}.gold_daily_kpi")
daily_kpi_count = spark.table(f"{GOLD_SCHEMA}.gold_daily_kpi").count()
print(f"gold_daily_kpi 保存完了: {daily_kpi_count:,} 件")


# ──────────────────────────────────────────────
# 2. gold_at_risk_users
#    粒度: snapshot_date(=AS_OF_DATE) × user_id
# ──────────────────────────────────────────────

# (a) ユーザーごとの最新サブスクリプション情報（直近のpayment_date順）
sub_recency_window = Window.partitionBy("user_id").orderBy(F.col("payment_date").desc())
subs_ranked = df_subs_enriched.withColumn("_rn", F.row_number().over(sub_recency_window))
latest_sub_per_user = subs_ranked.filter("_rn = 1").select(
    "user_id", "plan_type", F.col("payment_status").alias("last_payment_status")
)

# (b) 直近の決済からさかのぼって連続failed回数をカウント
is_failed_flag = subs_ranked.withColumn("_is_failed", (F.col("payment_status") == "failed").cast("int"))
running_window = Window.partitionBy("user_id").orderBy("_rn").rowsBetween(Window.unboundedPreceding, 0)
consecutive_failed_df = (
    is_failed_flag
    .withColumn("_running_min_failed", F.min("_is_failed").over(running_window))
    .groupBy("user_id")
    .agg(F.sum("_running_min_failed").alias("consecutive_failed_payments"))
)

# (c) 直近ログイン日からの経過日数
last_login_df = (
    df_silver_events.filter("event_type = 'login'")
    .groupBy("user_id")
    .agg(F.max(F.to_date("event_timestamp")).alias("last_login_date"))
    # datediffはIntegerTypeを返すが、Gold表はBIGINTで定義しているため明示的にキャストする
    .withColumn("days_since_last_login", F.datediff(F.lit(AS_OF_DATE), F.col("last_login_date")).cast("long"))
    .select("user_id", "days_since_last_login")
)

# (d) 直近30日間の解約クリック数（基準日はAS_OF_DATE）
cancel_click_30d_df = (
    df_silver_events
    .filter(
        (F.col("event_type") == "cancel_click")
        & (F.to_date(F.col("event_timestamp")) >= F.date_sub(F.lit(AS_OF_DATE), 30))
        & (F.to_date(F.col("event_timestamp")) <= F.lit(AS_OF_DATE))
    )
    .groupBy("user_id")
    .agg(F.count("*").alias("cancel_click_count_30d"))
)

df_at_risk = (
    df_silver_users.select("user_id", "country_code")
    .join(latest_sub_per_user, on="user_id", how="left")
    .join(consecutive_failed_df, on="user_id", how="left")
    .join(last_login_df, on="user_id", how="left")
    .join(cancel_click_30d_df, on="user_id", how="left")
    .withColumn("consecutive_failed_payments", F.coalesce(F.col("consecutive_failed_payments"), F.lit(0)))
    .withColumn("cancel_click_count_30d", F.coalesce(F.col("cancel_click_count_30d"), F.lit(0)))
    .withColumn(
        "churn_risk_level",
        F.when((F.col("consecutive_failed_payments") >= 2) | (F.col("cancel_click_count_30d") >= 2), F.lit("high"))
         .when((F.col("consecutive_failed_payments") == 1) | (F.col("cancel_click_count_30d") == 1), F.lit("medium"))
         .otherwise(F.lit("low")),
    )
    .withColumn(
        "risk_reason",
        F.nullif(
            F.concat_ws(
                ",",
                F.when(F.col("consecutive_failed_payments") > 0,
                       F.concat(F.lit("決済失敗"), F.col("consecutive_failed_payments"), F.lit("回連続"))),
                F.when(F.col("cancel_click_count_30d") > 0,
                       F.concat(F.lit("解約クリック"), F.col("cancel_click_count_30d"), F.lit("件(30日)"))),
            ),
            F.lit(""),
        ),
    )
    .withColumn("snapshot_date", F.lit(AS_OF_DATE))
    .select(
        "snapshot_date", "user_id", "country_code", "plan_type", "last_payment_status",
        "consecutive_failed_payments", "days_since_last_login", "cancel_click_count_30d",
        "churn_risk_level", "risk_reason",
    )
)

df_at_risk.write.format("delta").mode("overwrite").saveAsTable(f"{GOLD_SCHEMA}.gold_at_risk_users")
at_risk_count = spark.table(f"{GOLD_SCHEMA}.gold_at_risk_users").count()
print(f"gold_at_risk_users 保存完了: {at_risk_count:,} 件")


# ──────────────────────────────────────────────
# 3. gold_data_quality_summary
#    粒度: check_date(=本日) × source_table × quality_check_name
#    ※ この表はパイプライン監視用のため、基準日はAS_OF_DATEではなく
#      実際にチェックを実行した日（current_date）を使う
# ──────────────────────────────────────────────

BRONZE_SCHEMA = "bronze01"
df_bronze_users = spark.table(f"{BRONZE_SCHEMA}.bronze_users")
df_bronze_subs = spark.table(f"{BRONZE_SCHEMA}.bronze_subscriptions")
df_bronze_events = spark.table(f"{BRONZE_SCHEMA}.bronze_user_events")

JP_VARIANTS = ["jp", "jpn", "Japan", "JAPAN"]
VALID_STATUSES = ["success", "failed", "pending", "refunded"]
valid_user_ids_list = [r.user_id for r in df_bronze_users.select("user_id").collect()]

users_total = df_bronze_users.count()
subs_total = df_bronze_subs.count()
events_total = df_bronze_events.count()

dq_checks = [
    ("bronze_users", "country_code_variant",
     df_bronze_users.filter(F.col("country_code").isin(JP_VARIANTS)).count(), users_total, "low"),
    ("bronze_subscriptions", "user_id_null",
     df_bronze_subs.filter(F.col("user_id").isNull()).count(), subs_total, "high"),
    ("bronze_subscriptions", "user_id_orphan",
     df_bronze_subs.filter(F.col("user_id").isNotNull() & (~F.col("user_id").isin(valid_user_ids_list))).count(),
     subs_total, "high"),
    ("bronze_subscriptions", "payment_date_format_variant",
     df_bronze_subs.filter(~F.col("payment_date").rlike(r"^\d{4}-\d{2}-\d{2}$")).count(), subs_total, "low"),
    ("bronze_subscriptions", "invalid_amount",
     df_bronze_subs.filter(F.col("amount") <= 0).count(), subs_total, "high"),
    ("bronze_subscriptions", "invalid_payment_status",
     df_bronze_subs.filter(~F.col("payment_status").isin(VALID_STATUSES)).count(), subs_total, "medium"),
    ("bronze_user_events", "user_id_null",
     df_bronze_events.filter(F.col("user_id").isNull()).count(), events_total, "high"),
    ("bronze_user_events", "user_id_orphan",
     df_bronze_events.filter(F.col("user_id").isNotNull() & (~F.col("user_id").isin(valid_user_ids_list))).count(),
     events_total, "high"),
    ("bronze_user_events", "duplicate_event_id",
     df_bronze_events.groupBy("event_id").count().filter(F.col("count") > 1).agg(F.sum("count")).collect()[0][0] or 0,
     events_total, "medium"),
    ("bronze_user_events", "delayed_arrival",
     df_bronze_events.filter(
         (F.col("ingestion_timestamp").cast("long") - F.col("event_timestamp").cast("long")) >= 86400
     ).count(), events_total, "low"),
]

dq_rows = [
    (source_table, check_name, int(total), int(failed), (float(failed) / total if total > 0 else None), severity)
    for source_table, check_name, failed, total, severity in dq_checks
]

df_gold_dq_summary = spark.createDataFrame(
    dq_rows, schema=["source_table", "quality_check_name", "total_record_count", "failed_record_count",
                      "failed_record_ratio", "severity"]
).withColumn("check_date", F.current_date()).select(
    "check_date", "source_table", "quality_check_name", "total_record_count", "failed_record_count",
    "failed_record_ratio", "severity",
)

df_gold_dq_summary.write.format("delta").mode("overwrite").saveAsTable(f"{GOLD_SCHEMA}.gold_data_quality_summary")
dq_summary_count = spark.table(f"{GOLD_SCHEMA}.gold_data_quality_summary").count()
print(f"gold_data_quality_summary 保存完了: {dq_summary_count:,} 件")


# ──────────────────────────────────────────────
# 4. gold_user_ml_features
#    粒度: feature_date(=AS_OF_DATE) × user_id
# ──────────────────────────────────────────────

logins_30d = (
    df_silver_events.filter(
        (F.col("event_type") == "login")
        & (F.to_date("event_timestamp") >= F.date_sub(F.lit(AS_OF_DATE), 30))
        & (F.to_date("event_timestamp") <= F.lit(AS_OF_DATE))
    ).groupBy("user_id").agg(F.count("*").alias("total_logins_30d"))
)
feature_use_30d = (
    df_silver_events.filter(
        (F.col("event_type") == "feature_use")
        & (F.to_date("event_timestamp") >= F.date_sub(F.lit(AS_OF_DATE), 30))
        & (F.to_date("event_timestamp") <= F.lit(AS_OF_DATE))
    ).groupBy("user_id").agg(F.count("*").alias("total_feature_use_30d"))
)
upgrade_click_30d = (
    df_silver_events.filter(
        (F.col("event_type") == "upgrade_click")
        & (F.to_date("event_timestamp") >= F.date_sub(F.lit(AS_OF_DATE), 30))
        & (F.to_date("event_timestamp") <= F.lit(AS_OF_DATE))
    ).groupBy("user_id").agg(F.count("*").alias("upgrade_click_count_30d"))
)
cancel_click_30d_ml = cancel_click_30d_df.withColumnRenamed("cancel_click_count_30d", "cancel_click_count_30d_ml")
failed_payment_90d = (
    df_subs_enriched.filter(
        (F.col("payment_status") == "failed")
        & (F.col("payment_date") >= F.date_sub(F.lit(AS_OF_DATE), 90))
        & (F.col("payment_date") <= F.lit(AS_OF_DATE))
    ).groupBy("user_id").agg(F.count("*").alias("failed_payment_count_90d"))
)
revenue_to_date = (
    df_subs_enriched.filter((F.col("payment_status") == "success") & (F.col("payment_date") <= F.lit(AS_OF_DATE)))
    .groupBy("user_id").agg(F.sum("amount").alias("total_revenue_to_date"))
)
churn_label_df = (
    df_subs_enriched.groupBy("user_id")
    .agg(F.max(F.when(F.col("contract_end_date").isNotNull() & (F.col("contract_end_date") <= F.lit(AS_OF_DATE)), 1).otherwise(0))
         .alias("_has_churned"))
    .withColumn("is_churned_label", F.col("_has_churned") == 1)
    .select("user_id", "is_churned_label")
)

df_ml_features = (
    df_silver_users.select("user_id", "country_code", "signup_platform", "signup_date")
    # datediffはIntegerTypeを返すが、Gold表はBIGINTで定義しているため明示的にキャストする
    .withColumn("tenure_days", F.datediff(F.lit(AS_OF_DATE), F.col("signup_date")).cast("long"))
    .join(latest_sub_per_user.select("user_id", F.col("plan_type").alias("current_plan_type")), on="user_id", how="left")
    .join(logins_30d, on="user_id", how="left")
    .join(feature_use_30d, on="user_id", how="left")
    .join(upgrade_click_30d, on="user_id", how="left")
    .join(cancel_click_30d_ml, on="user_id", how="left")
    .join(failed_payment_90d, on="user_id", how="left")
    .join(revenue_to_date, on="user_id", how="left")
    .join(churn_label_df, on="user_id", how="left")
    .withColumn("total_logins_30d", F.coalesce(F.col("total_logins_30d"), F.lit(0)))
    .withColumn("total_feature_use_30d", F.coalesce(F.col("total_feature_use_30d"), F.lit(0)))
    .withColumn("upgrade_click_count_30d", F.coalesce(F.col("upgrade_click_count_30d"), F.lit(0)))
    .withColumn("cancel_click_count_30d", F.coalesce(F.col("cancel_click_count_30d_ml"), F.lit(0)))
    .withColumn("failed_payment_count_90d", F.coalesce(F.col("failed_payment_count_90d"), F.lit(0)))
    .withColumn("total_revenue_to_date", F.coalesce(F.col("total_revenue_to_date"), F.lit(0.0)))
    .withColumn("feature_date", F.lit(AS_OF_DATE))
    .select(
        "feature_date", "user_id", "country_code", "signup_platform", "tenure_days", "current_plan_type",
        "total_logins_30d", "total_feature_use_30d", "upgrade_click_count_30d", "cancel_click_count_30d",
        "failed_payment_count_90d", "total_revenue_to_date", "is_churned_label",
    )
)

df_ml_features.write.format("delta").mode("overwrite").saveAsTable(f"{GOLD_SCHEMA}.gold_user_ml_features")
ml_features_count = spark.table(f"{GOLD_SCHEMA}.gold_user_ml_features").count()
print(f"gold_user_ml_features 保存完了: {ml_features_count:,} 件")


# ──────────────────────────────────────────────
# 5. 保存結果サマリー
# ──────────────────────────────────────────────

print("\n" + "=" * 40)
print("=== Gold層 データ投入完了サマリー ===")
print("=" * 40)
print(f"  gold_daily_kpi            : {daily_kpi_count:>6,} 件")
print(f"  gold_at_risk_users        : {at_risk_count:>6,} 件")
print(f"  gold_data_quality_summary : {dq_summary_count:>6,} 件")
print(f"  gold_user_ml_features     : {ml_features_count:>6,} 件")
print("=" * 40)
