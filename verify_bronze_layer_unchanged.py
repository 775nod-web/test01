"""
Bronze レイヤー データ無加工検証スクリプト（Databricks Free Edition Notebook 用）

前提: save_bronze_layer_tables.py を実行済みで、
      bronze.customer_master / bronze.contract_data / bronze.support_tickets
      が Delta テーブルとして保存されていること。

取り込みメタデータ（ingested_at, source_system）を除いた業務データが、
sample スキーマの元データと完全に一致しているか（＝加工されていないか）を検証する。

検証項目:
  1. 件数が一致するか
  2. スキーマ（列名・型・nullable）が一致するか
  3. 行の内容が完全に一致するか（sample⇔bronze 双方向で差分行数が0件か）
"""

METADATA_COLUMNS = ["ingested_at", "source_system"]
TABLE_NAMES = ["customer_master", "contract_data", "support_tickets"]


def verify_unchanged(table_name: str) -> bool:
    """sample.<table_name> と bronze.<table_name>（メタデータ列を除く）を比較し、
    業務データが無加工で保存されているかを検証する"""
    df_sample = spark.table(f"sample.{table_name}")
    df_bronze_raw = spark.table(f"bronze.{table_name}").drop(*METADATA_COLUMNS)

    # (1) 件数比較
    sample_count = df_sample.count()
    bronze_count = df_bronze_raw.count()
    count_match = sample_count == bronze_count

    # (2) スキーマ比較（列名・型・nullable）
    schema_match = df_sample.schema == df_bronze_raw.schema

    # (3) 行内容の完全一致比較（双方向の差分が0件であること）
    only_in_sample = df_sample.exceptAll(df_bronze_raw).count()
    only_in_bronze = df_bronze_raw.exceptAll(df_sample).count()
    data_match = (only_in_sample == 0) and (only_in_bronze == 0)

    is_unchanged = count_match and schema_match and data_match

    print(f"--- {table_name} ---")
    print(f"  件数一致        : {count_match}（sample={sample_count}件 / bronze={bronze_count}件）")
    print(f"  スキーマ一致    : {schema_match}")
    print(f"  データ完全一致  : {data_match}（sampleのみに存在={only_in_sample}件 / bronzeのみに存在={only_in_bronze}件）")
    print(f"  判定            : {'OK（無加工で保存済み）' if is_unchanged else 'NG（差分あり・要確認）'}\n")

    return is_unchanged


print("=== Bronzeレイヤー データ無加工検証（sample との比較） ===\n")
verification_results = {name: verify_unchanged(name) for name in TABLE_NAMES}

df_verification_summary = spark.createDataFrame(
    [(name, "OK" if ok else "NG") for name, ok in verification_results.items()],
    ["table_name", "verification_result"],
)

print("=== 検証結果サマリ ===")
display(df_verification_summary)

all_ok = all(verification_results.values())
print(f"\n全表の検証結果: {'すべてOK（メタデータ以外は無加工で保存されている）' if all_ok else '一部NGあり（要確認）'}")
