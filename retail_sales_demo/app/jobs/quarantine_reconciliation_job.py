"""quarantine自動再照合バッチ（追加機能・優先度高）。

現行課題「マスター更新遅延で再処理が必要」を解消するための第一歩として、
gold_unregistered_master_report のうち、商品/店舗マスターが更新されたことで
現在は登録済みとなっている取引を検出し、件数をレポートする。

【スコープの注意】
実際にGold layerへ昇格（再計算）させるには、既存のSilver→Gold変換ロジックを
再実行する必要があり、これは本Serving layerタスクの範囲外（既存パイプライン側の改修）。
本ジョブは「再照合対象件数の可視化」と「再照合実行の記録」までを担う。

実ワークスペースで確認済み: Gold layerは workspace.gold、商品/店舗マスターは
workspace.silver.silver_product_master / workspace.silver.silver_store_master。
"""
import os

from pyspark.sql import SparkSession

CATALOG = os.environ.get("GOLD_CATALOG", "workspace")
SCHEMA = os.environ.get("GOLD_SCHEMA", "gold")
SILVER_SCHEMA = os.environ.get("SILVER_SCHEMA", "silver")
PRODUCTS_TABLE = os.environ.get("PRODUCTS_MASTER_TABLE", f"{CATALOG}.{SILVER_SCHEMA}.silver_product_master")
STORES_TABLE = os.environ.get("STORES_MASTER_TABLE", f"{CATALOG}.{SILVER_SCHEMA}.silver_store_master")


def main() -> None:
    spark = SparkSession.builder.getOrCreate()

    quarantine = spark.table(f"{CATALOG}.{SCHEMA}.gold_unregistered_master_report")
    products = spark.table(PRODUCTS_TABLE).select("product_id").distinct()
    stores = spark.table(STORES_TABLE).select("store_id").distinct()

    reconcilable_count = (
        quarantine.join(products, on="product_id", how="inner")
        .join(stores, on="store_id", how="inner")
        .count()
    )

    print(f"[quarantine_reconciliation_job] 再照合対象（登録済みになった取引）件数: {reconcilable_count}")

    # 再照合ログを残す（監査・進捗管理用）。テーブルが無ければ作成する。
    spark.sql(
        f"""
        CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.quarantine_reconciliation_log (
            run_timestamp TIMESTAMP,
            reconcilable_count BIGINT
        )
        """
    )
    spark.sql(
        f"""
        INSERT INTO {CATALOG}.{SCHEMA}.quarantine_reconciliation_log
        VALUES (current_timestamp(), {reconcilable_count})
        """
    )

    # 実際のGold再計算（quarantineからの昇格・削除）は既存のSilver→Goldパイプライン側で
    # 実施する。ここでは対象件数の可視化までに留める。


if __name__ == "__main__":
    main()
