"""Phase 3-E: quarantine re-match candidate check.

Scope note (per the Phase 3 prompt): actually recomputing Gold from Silver so
that resolved records leave gold_unregistered_master_report is the existing
Bronze/Silver/Gold pipeline's responsibility, not this Serving layer add-on.
This job only detects and counts which currently-quarantined records *would*
now resolve against the latest silver_product_master / silver_store_master,
so operators can see whether triggering a full pipeline re-run is worth it.
It does NOT modify gold_unregistered_master_report.

Runs as a Databricks Jobs Python task (see resources/requeue_batch_job.json),
triggered on demand via POST /api/requeue-trigger (Jobs API run-now) or on a
schedule if one is added later. GET /api/requeue-status reads the latest row
this script writes to gold_requeue_batch_runs.

*** NOT RUN OR VERIFIED ***: same caveat as jobs/alert_batch.py — no
Databricks workspace access from this coding session, so this has never run
against real data or a confirmed schema.
"""
import uuid
from datetime import datetime, timezone

from pyspark.sql import SparkSession, functions as F

GOLD_CATALOG = "workspace"
GOLD_SCHEMA = "gold"
SILVER_SCHEMA = "silver"

QUARANTINE_TABLE = f"{GOLD_CATALOG}.{GOLD_SCHEMA}.gold_unregistered_master_report"
PRODUCT_MASTER_TABLE = f"{GOLD_CATALOG}.{SILVER_SCHEMA}.silver_product_master"
STORE_MASTER_TABLE = f"{GOLD_CATALOG}.{SILVER_SCHEMA}.silver_store_master"
RUNS_TABLE = f"{GOLD_CATALOG}.{GOLD_SCHEMA}.gold_requeue_batch_runs"


def main() -> None:
    spark = SparkSession.builder.getOrCreate()
    run_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)
    status = "SUCCEEDED"
    checked = 0
    reconciled_count = 0

    try:
        quarantined = spark.table(QUARANTINE_TABLE)
        known_products = spark.table(PRODUCT_MASTER_TABLE).select(
            F.col("product_id").alias("_known_product_id")
        ).distinct()
        known_stores = spark.table(STORE_MASTER_TABLE).select(F.col("store_id").alias("_known_store_id")).distinct()

        checked = quarantined.count()

        reconciled_candidates = (
            quarantined.join(known_products, quarantined.product_id == known_products._known_product_id, "left")
            .join(known_stores, quarantined.store_id == known_stores._known_store_id, "left")
            .filter(F.col("_known_product_id").isNotNull() & F.col("_known_store_id").isNotNull())
        )
        reconciled_count = reconciled_candidates.count()
    except Exception as exc:  # noqa: BLE001 — record the failure in the run log below
        status = "FAILED"
        print(f"[requeue_batch] failed: {exc}")

    spark.sql(
        f"""
        CREATE TABLE IF NOT EXISTS {RUNS_TABLE} (
            run_id STRING,
            started_at TIMESTAMP,
            status STRING,
            records_checked INT,
            reconciled_candidates_found INT
        ) USING DELTA
        """
    )
    spark.createDataFrame(
        [(run_id, started_at, status, checked, reconciled_count)],
        schema=(
            "run_id STRING, started_at TIMESTAMP, status STRING, "
            "records_checked INT, reconciled_candidates_found INT"
        ),
    ).write.mode("append").format("delta").saveAsTable(RUNS_TABLE)

    print(f"[requeue_batch] run_id={run_id} status={status} checked={checked} reconciled_candidates={reconciled_count}")
    print(
        "[requeue_batch] NOTE: reconciled candidates are NOT removed from "
        "gold_unregistered_master_report by this job. That requires "
        "re-running the existing Silver->Gold pipeline so Gold recomputes "
        "without these now-resolved rows."
    )


if __name__ == "__main__":
    main()
