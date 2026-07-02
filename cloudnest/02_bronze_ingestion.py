"""
CloudNest Bronze レイヤー取り込みスクリプト（Databricks ノートブック用）
======================================================
01_generate_sample_data.py で生成したテンポラリビューを、
Bronze レイヤー（生データそのまま＋取り込みメタデータ）として Delta テーブルに保存する。

本番PoCでは、ここが以下のような実ソースシステムからの取り込みに置き換わる：
  - customer_master  ← CRM（Salesforce等）/ LakeFlow Connect
  - contracts         ← 契約管理システム / CRM
  - usage_logs        ← プロダクトのイベントストリーム（Kafka/Kinesis等）→ Structured Streaming や Auto Loader
  - support_tickets    ← Zendesk / Freshdesk 等 → LakeFlow Connect コネクタ
  - billing            ← Stripe等の請求システム / CRM

前提：01_generate_sample_data.py を同セッションで実行済みであること
動作確認環境：Databricks Free Edition（Unity Catalog 不使用・Hive メタストア）
  ※ Unity Catalog 環境では database 名を `<catalog>.bronze` 等に読み替える
"""

from pyspark.sql import functions as F

# ──────────────────────────────────────────────
# 0. 保存先データベース（スキーマ）の作成
# ──────────────────────────────────────────────

spark.sql("CREATE DATABASE IF NOT EXISTS bronze")
spark.sql("USE bronze")
print("データベース 'bronze' を選択しました")


def save_bronze_table(view_name: str, table_name: str, source_system: str):
    """テンポラリビューを取り込みメタデータ付きで Bronze Delta テーブルとして保存する"""
    df = spark.table(view_name).withColumn(
        "_ingested_at", F.current_timestamp()
    ).withColumn(
        "_source_system", F.lit(source_system)
    )
    (
        df.write
        .format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable(f"bronze.{table_name}")
    )
    count = spark.table(f"bronze.{table_name}").count()
    print(f"{table_name} 保存完了: {count:,} 件 （source_system={source_system}）")
    return count


# ──────────────────────────────────────────────
# 1. 各ソースを Bronze テーブルへ保存
# ──────────────────────────────────────────────

counts = {}
counts["cloudnest_bronze_customer_master"] = save_bronze_table(
    "cloudnest_customer_master", "cloudnest_bronze_customer_master", "crm")
counts["cloudnest_bronze_contracts"] = save_bronze_table(
    "cloudnest_contracts", "cloudnest_bronze_contracts", "crm")
counts["cloudnest_bronze_usage_logs"] = save_bronze_table(
    "cloudnest_usage_logs", "cloudnest_bronze_usage_logs", "product_event_stream")
counts["cloudnest_bronze_support_tickets"] = save_bronze_table(
    "cloudnest_support_tickets", "cloudnest_bronze_support_tickets", "support_desk")
counts["cloudnest_bronze_billing"] = save_bronze_table(
    "cloudnest_billing", "cloudnest_bronze_billing", "billing_system")


# ──────────────────────────────────────────────
# 2. 保存結果サマリー
# ──────────────────────────────────────────────

print("\n" + "=" * 50)
print("=== CloudNest Bronze レイヤー 保存完了サマリー ===")
print("=" * 50)
for name, cnt in counts.items():
    print(f"  {name:<38}: {cnt:>8,} 件")
print("=" * 50)

# Delta 履歴確認（監査証跡・タイムトラベルの元となる）
print("\n=== cloudnest_bronze_customer_master の Delta 履歴 ===")
spark.sql("DESCRIBE HISTORY bronze.cloudnest_bronze_customer_master").select(
    "version", "timestamp", "operation", "operationParameters"
).show(truncate=False)
