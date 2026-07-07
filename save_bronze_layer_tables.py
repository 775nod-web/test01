"""
Bronze レイヤー保存スクリプト（Databricks Free Edition Notebook 用）

前提: generate_and_save_sample_data.py を実行済みで、
      sample.customer_master / sample.contract_data / sample.support_tickets
      が Delta テーブルとして保存されていること。

sample スキーマの業務データ（列の値）は一切変更せず、Bronzeレイヤーの
取り込みメタデータ（取り込み日時 ingested_at、データソース source_system）
のみを追加して bronze スキーマの Delta テーブルとして保存する。

型変換・欠損補完・重複排除・表記統一などのデータクレンジングは
Silverレイヤーで実施するため、ここでは一切行わない
（Bronzeは生データをそのまま保持する層のため）。
"""

from pyspark.sql import functions as F

# ──────────────────────────────────────────────
# 0. 保存先スキーマの作成（無ければ作成）
# ──────────────────────────────────────────────

spark.sql("CREATE SCHEMA IF NOT EXISTS bronze")
print("スキーマ 'bronze' を選択しました（存在しない場合は作成済み）")


# ──────────────────────────────────────────────
# 共通処理: sample スキーマのテーブルを取り込みメタデータのみ付与して
#           bronze スキーマの Delta テーブルとして保存する
# ──────────────────────────────────────────────

def save_as_bronze(source_table: str, target_table: str, source_system: str) -> None:
    """業務データ列は無加工のまま、取り込みメタデータ2列のみ追加して保存する"""
    df_with_metadata = (
        spark.table(source_table)
        .withColumn("ingested_at", F.current_timestamp())    # 取り込み日時（メタデータ）
        .withColumn("source_system", F.lit(source_system))   # データソース（メタデータ）
    )

    (
        df_with_metadata
        .write.format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable(target_table)
    )

    print(f"{target_table} 保存完了: {spark.table(target_table).count()} 件")


# ──────────────────────────────────────────────
# 1. 顧客マスター → bronze.customer_master
# ──────────────────────────────────────────────

save_as_bronze(
    source_table="sample.customer_master",
    target_table="bronze.customer_master",
    source_system="カスタマーマスター",
)

# ──────────────────────────────────────────────
# 2. 契約データ → bronze.contract_data
# ──────────────────────────────────────────────

save_as_bronze(
    source_table="sample.contract_data",
    target_table="bronze.contract_data",
    source_system="コントラクトデータ",
)

# ──────────────────────────────────────────────
# 3. サポートチケット → bronze.support_tickets
# ──────────────────────────────────────────────

save_as_bronze(
    source_table="sample.support_tickets",
    target_table="bronze.support_tickets",
    source_system="サポートチケッツ",
)

print("\n=== bronze スキーマへの保存が完了しました ===")
print("  bronze.customer_master")
print("  bronze.contract_data")
print("  bronze.support_tickets")
