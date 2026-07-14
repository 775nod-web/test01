# Databricks notebook source
# MAGIC %md
# MAGIC # Phase 7 (OPTIONAL) — Baseline ML Churn Comparison
# MAGIC
# MAGIC **Optional Tier 2 enhancement. The mandatory demo (Phases 1-6) never
# MAGIC depends on anything produced here.** Compares the mandatory rule-based
# MAGIC risk score against two simple logistic-regression baselines (static
# MAGIC attributes only, and integrated Customer 360 behavior features) against
# MAGIC `churn_label_90d` — a **simulated** ground-truth label, not a real
# MAGIC outcome. See `docs/ml-comparison.md` for the full write-up and honest
# MAGIC reading of results, and `docs/risk-scoring.md` for the rule-based score
# MAGIC this compares against.
# MAGIC
# MAGIC Requires `pandas`, `scikit-learn`, `mlflow` — install via
# MAGIC `%pip install -r requirements-dev.txt` if not already on the cluster.
# MAGIC Uses MLflow's default tracking URI, which Databricks routes to the
# MAGIC workspace-hosted tracking server automatically when run as a notebook —
# MAGIC nothing here hardcodes a tracking URI.
# MAGIC
# MAGIC Run after `03_build_risk_and_retention.py`.

# COMMAND ----------

dbutils.widgets.text("catalog", "bank_demo", "Unity Catalog catalog name (used only if UC is enabled)")
dbutils.widgets.text("gold_schema", "gold", "Schema/database name for Gold tables")

catalog = dbutils.widgets.get("catalog")
gold_schema = dbutils.widgets.get("gold_schema")

# COMMAND ----------

import os
import sys

lib_dir = os.path.join(os.getcwd(), "lib")
if lib_dir not in sys.path:
    sys.path.append(lib_dir)

try:
    from catalog_utils import resolve_schema_prefix
    import ml_baseline
except ImportError as exc:
    raise ImportError(
        "Could not import notebooks/lib/{catalog_utils,ml_baseline}.py. Run "
        "this notebook from a Databricks Repo (Git folder) with the "
        "repository's folder structure intact, and install "
        "requirements-dev.txt (pandas, scikit-learn, mlflow) on the cluster."
    ) from exc

gold_prefix = resolve_schema_prefix(spark, catalog, gold_schema)
print(f"gold={gold_prefix}")

# COMMAND ----------

# MAGIC %md ## Load Gold tables into pandas (small: one row per customer)

# COMMAND ----------

customer_360_pd = spark.table(f"{gold_prefix}.customer_360").toPandas()
retention_pd = spark.table(f"{gold_prefix}.retention_action_list").toPandas()
customer_360_rows = customer_360_pd.to_dict(orient="records")
retention_rows = retention_pd.to_dict(orient="records")
print(f"Loaded {len(customer_360_rows):,} customers")

# COMMAND ----------

# MAGIC %md ## Run the three-way comparison (shared held-out test split)

# COMMAND ----------

comparison = ml_baseline.run_comparison(customer_360_rows, retention_rows)
for name, result in comparison.items():
    print(f"\n{name}: precision={result['precision']} recall={result['recall']} roc_auc={result['roc_auc']}")
    print(f"  confusion_matrix={result['confusion_matrix']}  n_train={result['n_train']} n_test={result['n_test']}")

# COMMAND ----------

# MAGIC %md ## Log to MLflow (best-effort — never blocks the comparison itself)

# COMMAND ----------

try:
    import mlflow

    mlflow.set_experiment("/Shared/bank_demo_phase7_ml_comparison")
    for name, result in comparison.items():
        with mlflow.start_run(run_name=name):
            mlflow.log_param("model_name", result["model_name"])
            mlflow.log_param("n_train", result["n_train"])
            mlflow.log_param("n_test", result["n_test"])
            mlflow.log_metric("precision", result["precision"])
            mlflow.log_metric("recall", result["recall"])
            mlflow.log_metric("roc_auc", result["roc_auc"])
    print("Logged all three runs to MLflow experiment /Shared/bank_demo_phase7_ml_comparison")
except Exception as exc:
    print(
        f"MLflow logging skipped ({type(exc).__name__}: {exc}). This is "
        f"optional instrumentation — the comparison above is unaffected."
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## Optional: write `gold.churn_model_scores` (batch scores only, no serving)
# MAGIC
# MAGIC Fits the behavioral-features model on the FULL population (not just the
# MAGIC comparison's train split) to produce one batch score per customer. This
# MAGIC table is never read by the mandatory app.

# COMMAND ----------

from pyspark.sql.types import DoubleType, StringType, StructField, StructType

df = ml_baseline.build_customer_frame(customer_360_rows, retention_rows)
X_full = ml_baseline.build_behavioral_features(df)
y_full = df["churn_label_90d"]

from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

scaler = StandardScaler()
X_scaled = scaler.fit_transform(X_full)
final_model = LogisticRegression(max_iter=1000, class_weight="balanced", random_state=ml_baseline.RANDOM_STATE)
final_model.fit(X_scaled, y_full)
probabilities = final_model.predict_proba(X_scaled)[:, 1]

scores_pd = df[["customer_id"]].copy()
scores_pd["ml_churn_probability"] = probabilities
scores_pd["model_name"] = "behavioral_features_logreg_v1"

scores_schema = StructType(
    [
        StructField("customer_id", StringType(), False),
        StructField("ml_churn_probability", DoubleType(), False),
        StructField("model_name", StringType(), False),
    ]
)
scores_df = spark.createDataFrame(scores_pd, schema=scores_schema)

spark.sql(f"DROP TABLE IF EXISTS {gold_prefix}.churn_model_scores")
scores_df.write.format("delta").mode("overwrite").saveAsTable(f"{gold_prefix}.churn_model_scores")
print(f"Wrote {gold_prefix}.churn_model_scores: {scores_df.count():,} rows (OPTIONAL — not used by the core app)")

# COMMAND ----------

print("Phase 7 (optional) complete. The mandatory app is unaffected by anything in this notebook.")
print("See docs/ml-comparison.md for the full write-up.")
