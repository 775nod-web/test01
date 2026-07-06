# Databricks ノートブック用
# Bronze01テーブルが「取り込みメタデータ列を除き」サンプルデータを
# 一切変更せずに保存できているかを検証する
#
# 前提：generate_cloudbox_sample_data.py と save_bronze01_tables.py を
#       同セッションで実行済みであること
#       （df_users / df_subscriptions / df_events と
#         bronze01.bronze_users / bronze_subscriptions / bronze_user_events が存在すること）
#
# 検証方法：
#   1. Bronze表から取り込みメタデータ列（_bronze_ingested_at, _bronze_source）を除外する
#   2. 生成直後のサンプルDataFrame（df_users等）と exceptAll で双方向に差分を取る
#      （exceptAllは重複行も区別して比較するため、event_id重複のような
#        意図的な重複行が保持されているかも含めて厳密に検証できる）
#   3. 件数一致・スキーマ（列名/型）一致もあわせて確認する

BRONZE_SCHEMA = "bronze01"
METADATA_COLUMNS = ["_bronze_ingested_at", "_bronze_source"]


def schema_signature(schema):
    """列名とデータ型のみを比較対象にする（nullableフラグは比較しない）。
    Delta保存時にNOT NULL制約がnullable=trueへ緩和される既知の仕様があり、
    これはデータ内容の変化ではないため、生データ一致検証の対象から除外する。"""
    return [(f.name, f.dataType) for f in schema.fields]


SOURCE_TABLE_MAP = {
    "bronze_users": df_users,
    "bronze_subscriptions": df_subscriptions,
    "bronze_user_events": df_events,
}

print("=" * 60)
print(f"{BRONZE_SCHEMA} 生データ整合性検証（取り込みメタデータを除く）")
print("=" * 60)

all_passed = True

for table_name, df_source in SOURCE_TABLE_MAP.items():
    full_name = f"{BRONZE_SCHEMA}.{table_name}"
    df_bronze_raw = spark.table(full_name)

    # 取り込みメタデータ列を除いたビジネスカラムのみを取り出す
    df_bronze_business = df_bronze_raw.drop(*METADATA_COLUMNS)

    print(f"\n--- {full_name} ---")

    # (a) 件数一致
    source_count = df_source.count()
    bronze_count = df_bronze_business.count()
    count_match = source_count == bronze_count
    print(f"件数一致: {count_match}  (サンプル: {source_count} 件 / Bronze: {bronze_count} 件)")

    # (b) 列名・型一致（ビジネスカラムのみ。nullableフラグは比較対象外）
    schema_match = schema_signature(df_source.schema) == schema_signature(df_bronze_business.schema)
    print(f"スキーマ一致（列名・型、ビジネスカラムのみ）: {schema_match}")

    # (c) データそのものの一致（重複行も区別する多重集合比較）
    only_in_source = df_source.exceptAll(df_bronze_business)
    only_in_bronze = df_bronze_business.exceptAll(df_source)
    only_in_source_count = only_in_source.count()
    only_in_bronze_count = only_in_bronze.count()
    data_match = (only_in_source_count == 0) and (only_in_bronze_count == 0)

    print(f"サンプルのみに存在する行: {only_in_source_count} 件")
    print(f"Bronzeのみに存在する行: {only_in_bronze_count} 件")
    print(f"データ完全一致（加工なしで保存できているか）: {data_match}")

    table_passed = count_match and schema_match and data_match
    all_passed = all_passed and table_passed
    print(f"[{table_name}] 検証結果: {'PASS' if table_passed else 'FAIL'}")

print("\n" + "=" * 60)
if all_passed:
    print("=== 総合検証結果: 全表PASS（生データは加工されずにそのまま保存されている） ===")
else:
    print("=== 総合検証結果: FAILあり。差分内容を確認してください ===")
print("=" * 60)
