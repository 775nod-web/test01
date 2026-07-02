"""
CloudNest 解約予測ベースラインモデル（Databricks ノートブック用・Phase 2 プレビュー）
======================================================
課題6「データサイエンスチームが解約予測モデルを作りたいが、信頼できるCustomer 360データがない」
への回答として、Silver層から時点整合性（point-in-time correctness）を担保した特徴量を作り、
MLflow でトラッキングしたベースライン分類モデルを学習する。

  ★ 本ノートブックは「本格的な解約予測モデル」ではなく、Customer 360が整備されれば
    すぐにモデル開発に着手できることを示す Phase 2 プレビュー（叩き台）という位置づけ。

【時点整合性（リーケージ防止）の設計】
  解約済み顧客の特徴量を「解約日時点」で計算すると、解約直前で利用率がほぼ0になり
  モデルが本質的でないパターンを学習してしまう（リーケージ）。
  そこで、各顧客の特徴量スナップショット日（feature_asof_date）を以下のように定義する：
    - 解約済み顧客：解約日の30日前（＝まだ介入の余地があったはずの時点）
    - 現役顧客　　：現在時点
  これにより「解約が起きる30日前に検知できるか」という実務的に意味のある学習データになる。

前提：03_silver_transformation.py まで実行済みであること
"""

from pyspark.sql import functions as F
import mlflow
import mlflow.spark
from pyspark.ml import Pipeline
from pyspark.ml.feature import StringIndexer, OneHotEncoder, VectorAssembler
from pyspark.ml.classification import GBTClassifier
from pyspark.ml.evaluation import BinaryClassificationEvaluator, MulticlassClassificationEvaluator

spark.sql("USE gold")

# ──────────────────────────────────────────────
# 1. 顧客ごとの特徴量スナップショット日（feature_asof_date）を決定
# ──────────────────────────────────────────────

df_customers = spark.table("silver.cloudnest_silver_customer_master").alias("cust")
df_contracts = spark.table("silver.cloudnest_silver_contracts").alias("ctr")

df_asof = (
    df_customers
    .join(df_contracts, F.col("cust.customer_id") == F.col("ctr.customer_id"), "inner")
    .select(
        F.col("cust.customer_id").alias("customer_id"),
        "is_churned", "churn_date", "industry", "employee_band", "region",
        "plan", "arr_usd", "licensed_seats", "contract_end_date", "contract_start_date",
    )
    .withColumn(
        "feature_asof_date",
        F.when(F.col("is_churned"), F.date_sub(F.col("churn_date"), 30)).otherwise(F.current_date())
    )
    # スナップショット日が契約開始日より前になってしまう（契約直後に解約した）ケースは除外
    .filter(F.col("feature_asof_date") >= F.col("contract_start_date"))
    .withColumn("days_to_renewal_asof", F.datediff("contract_end_date", "feature_asof_date"))
)

print(f"学習対象顧客数（point-in-time フィルタ後）: {df_asof.count():,} 件")
df_asof.groupBy("is_churned").count().show()


# ──────────────────────────────────────────────
# 2. 各顧客の feature_asof_date を基準に、利用ログ／チケット／請求の特徴量を結合
#    （範囲結合：usage_date が feature_asof_date 基準の直近30日/90日/180日以内）
# ──────────────────────────────────────────────

a = df_asof.alias("a")
u = spark.table("silver.cloudnest_silver_usage_daily").alias("u")

df_usage_recent = (
    a.join(u, (F.col("u.customer_id") == F.col("a.customer_id"))
           & (F.col("u.usage_date") > F.date_sub(F.col("a.feature_asof_date"), 30))
           & (F.col("u.usage_date") <= F.col("a.feature_asof_date")), "left")
    .groupBy(F.col("a.customer_id").alias("customer_id"))
    .agg(F.avg("u.daily_active_users").alias("avg_dau_last_30d"))
)

df_usage_prior = (
    a.join(u, (F.col("u.customer_id") == F.col("a.customer_id"))
           & (F.col("u.usage_date") > F.date_sub(F.col("a.feature_asof_date"), 60))
           & (F.col("u.usage_date") <= F.date_sub(F.col("a.feature_asof_date"), 30)), "left")
    .groupBy(F.col("a.customer_id").alias("customer_id"))
    .agg(F.avg("u.daily_active_users").alias("avg_dau_prior_30d"))
)

priority_weight = F.when(F.col("t.priority") == "Critical", 4).when(F.col("t.priority") == "High", 3) \
    .when(F.col("t.priority") == "Medium", 2).otherwise(1)
t = spark.table("silver.cloudnest_silver_support_tickets").alias("t")
df_tickets_feat = (
    a.join(t, (F.col("t.customer_id") == F.col("a.customer_id"))
           & (F.col("t.created_date") > F.date_sub(F.col("a.feature_asof_date"), 90))
           & (F.col("t.created_date") <= F.col("a.feature_asof_date")), "left")
    .withColumn("_pw", priority_weight)
    .groupBy(F.col("a.customer_id").alias("customer_id"))
    .agg(
        F.count("t.ticket_id").alias("tickets_last_90d"),
        F.avg("_pw").alias("avg_ticket_priority_weight"),
        F.avg("t.csat_score").alias("avg_csat_last_90d"),
    )
)

b = spark.table("silver.cloudnest_silver_billing").alias("b")
df_billing_feat = (
    a.join(b, (F.col("b.customer_id") == F.col("a.customer_id"))
           & (F.col("b.billing_date") > F.date_sub(F.col("a.feature_asof_date"), 180))
           & (F.col("b.billing_date") <= F.col("a.feature_asof_date")), "left")
    .groupBy(F.col("a.customer_id").alias("customer_id"))
    .agg(
        F.sum(F.when(F.col("b.payment_status") == "Overdue", 1).otherwise(0)).alias("overdue_invoices"),
        F.sum(F.when(F.col("b.plan_change_type") == "Downgrade", 1).otherwise(0)).alias("downgrades"),
    )
)

df_training = (
    df_asof
    .join(df_usage_recent, "customer_id", "left")
    .join(df_usage_prior, "customer_id", "left")
    .join(df_tickets_feat, "customer_id", "left")
    .join(df_billing_feat, "customer_id", "left")
    .withColumn(
        "usage_trend_pct",
        F.when(F.col("avg_dau_prior_30d").isNull() | (F.col("avg_dau_prior_30d") == 0),
               F.when(F.col("avg_dau_last_30d") > 0, F.lit(1.0)).otherwise(F.lit(0.0)))
        .otherwise((F.col("avg_dau_last_30d") - F.col("avg_dau_prior_30d")) / F.col("avg_dau_prior_30d"))
    )
    .fillna({
        "tickets_last_90d": 0, "avg_ticket_priority_weight": 1.0, "avg_csat_last_90d": 3.5,
        "overdue_invoices": 0, "downgrades": 0, "avg_dau_last_30d": 0.0,
    })
    .withColumn("label", F.col("is_churned").cast("int"))
)

feature_cols_categorical = ["industry", "employee_band", "region", "plan"]
# 注意：days_to_renewal_asof はこのプロトタイプの学習特徴量からは除外する。
# 本データ生成ロジックでは「解約＝契約終了日」として定義しているため、解約顧客は
# contract_end_date が churn_date と一致し、feature_asof_date（churn_date-30日）からの
# 残日数が常に一定値になってしまう（リーケージ）。実データではこのような構造的な
# 一致は生じないため、実データPoCでは残日数も有効な特徴量として利用できる。
feature_cols_numeric = [
    "arr_usd", "licensed_seats", "usage_trend_pct",
    "tickets_last_90d", "avg_ticket_priority_weight", "avg_csat_last_90d",
    "overdue_invoices", "downgrades",
]

print(f"\n学習データセット行数: {df_training.count():,} 件 / 特徴量数: {len(feature_cols_categorical) + len(feature_cols_numeric)}")


# ──────────────────────────────────────────────
# 3. MLflow でトラッキングしながらベースラインモデル（GBTClassifier）を学習
# ──────────────────────────────────────────────

mlflow.set_experiment("/Shared/cloudnest_churn_prediction_baseline")

train_df, test_df = df_training.randomSplit([0.75, 0.25], seed=42)

indexers = [StringIndexer(inputCol=c, outputCol=f"{c}_idx", handleInvalid="keep") for c in feature_cols_categorical]
encoders = [OneHotEncoder(inputCol=f"{c}_idx", outputCol=f"{c}_ohe") for c in feature_cols_categorical]
assembler = VectorAssembler(
    inputCols=[f"{c}_ohe" for c in feature_cols_categorical] + feature_cols_numeric,
    outputCol="features",
    handleInvalid="skip",
)
gbt = GBTClassifier(labelCol="label", featuresCol="features", maxIter=50, maxDepth=4, seed=42)
pipeline = Pipeline(stages=indexers + encoders + [assembler, gbt])

with mlflow.start_run(run_name="cloudnest_churn_gbt_baseline") as run:
    mlflow.log_param("model_type", "GBTClassifier")
    mlflow.log_param("max_iter", 50)
    mlflow.log_param("max_depth", 4)
    mlflow.log_param("training_rows", train_df.count())
    mlflow.log_param("feature_count", len(feature_cols_categorical) + len(feature_cols_numeric))

    model = pipeline.fit(train_df)
    predictions = model.transform(test_df)

    auc = BinaryClassificationEvaluator(labelCol="label", metricName="areaUnderROC").evaluate(predictions)
    accuracy = MulticlassClassificationEvaluator(labelCol="label", metricName="accuracy").evaluate(predictions)
    f1 = MulticlassClassificationEvaluator(labelCol="label", metricName="f1").evaluate(predictions)

    mlflow.log_metric("test_auc", auc)
    mlflow.log_metric("test_accuracy", accuracy)
    mlflow.log_metric("test_f1", f1)
    mlflow.spark.log_model(model, "model")

    print(f"\n=== MLflow Run: {run.info.run_id} ===")
    print(f"  Test AUC      : {auc:.3f}")
    print(f"  Test Accuracy : {accuracy:.3f}")
    print(f"  Test F1       : {f1:.3f}")

    # 特徴量重要度 → ヘルススコアの重み設計（40/25/15/20%）が学習結果と整合しているかを検証する
    gbt_model = model.stages[-1]
    importances = list(zip(assembler.getInputCols(), gbt_model.featureImportances.toArray()))
    importances.sort(key=lambda x: -x[1])
    print("\n=== 特徴量重要度 Top 10（ルールベースのヘルススコア設計との答え合わせ） ===")
    for name, score in importances[:10]:
        print(f"  {name:<30}: {score:.4f}")


# ──────────────────────────────────────────────
# 4. 予測結果を Gold テーブルとして保存（デモ・検証用）
# ──────────────────────────────────────────────

df_predictions_out = predictions.select(
    "customer_id", "label", "prediction", "probability", "feature_asof_date"
)
(df_predictions_out.write.format("delta").mode("overwrite")
 .option("overwriteSchema", "true").saveAsTable("gold.cloudnest_gold_churn_prediction_baseline"))

print("\ngold.cloudnest_gold_churn_prediction_baseline に予測結果を保存しました。")
print("\n[本番化に向けた次のステップ]")
print(" 1. Databricks Feature Store で特徴量をバージョン管理し、学習/推論間の一貫性を担保")
print(" 2. より長期間・全顧客（3,000社）の履歴データで再学習し、Champion/Challenger運用")
print(" 3. Model Serving でリアルタイム/バッチ推論エンドポイントを構築し、Customer 360に予測値を還元")
print(" 4. MLflow Model Registry でモデルのライフサイクル（Staging→Production）を管理")
print(" 5. CSMのフィードバック（予測は正しかったか）を再学習ループに組み込み、継続的に精度改善")
