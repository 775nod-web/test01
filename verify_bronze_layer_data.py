"""
Bronze layer 生データ整合性検証スクリプト
- sample スキーマ（生成直後のサンプルデータ）と bronze スキーマ（Bronze layer保存後）を比較し、
  取り込みメタデータ列（ingested_at / source_system）を除いた「生データ部分」が
  一切変更されずに保存されているかを検証する

検証項目（表ごと）:
  1. 件数が一致しているか
  2. 追加された列が想定どおり（ingested_at, source_system のみ）か
  3. 元の列が欠落・リネームされていないか
  4. 値の内容が完全一致しているか（重複行を含む多重集合として比較 = exceptAll）
  5. 元の列のスキーマ（型・Nullable）が変化していないか

前提: generate_fraud_sample_data.py と save_bronze_layer_tables.py を先に実行し、
      sample / bronze 両スキーマにテーブルが作成済みであること
動作確認環境: Databricks Free Edition
"""

METADATA_COLUMNS = ["ingested_at", "source_system"]

TABLE_PAIRS = [
    ("customers",    "sample.bronze_customers",    "bronze.customers"),
    ("accounts",     "sample.bronze_accounts",     "bronze.accounts"),
    ("transactions", "sample.bronze_transactions", "bronze.transactions"),
]

all_passed = True
results = []

for label, sample_table, bronze_table in TABLE_PAIRS:
    df_sample = spark.table(sample_table)
    df_bronze = spark.table(bronze_table)

    sample_columns = df_sample.columns
    bronze_columns = df_bronze.columns

    # (2)(3) 列構成のチェック：追加された列・欠落した列
    added_columns = set(bronze_columns) - set(sample_columns)
    missing_columns = set(sample_columns) - set(bronze_columns)
    columns_ok = (added_columns == set(METADATA_COLUMNS)) and (len(missing_columns) == 0)

    # (1) 件数チェック
    sample_count = df_sample.count()
    bronze_count = df_bronze.count()
    count_ok = sample_count == bronze_count

    # (5) 元の列のスキーマ（型・Nullable）が変わっていないか
    df_bronze_business = df_bronze.select(*sample_columns)  # 生データ部分のみ抽出（列順もsampleに合わせる）
    schema_ok = df_sample.schema == df_bronze_business.schema

    # (4) 値の内容が完全一致しているか（重複行も含めた多重集合比較）
    only_in_sample = df_sample.exceptAll(df_bronze_business)
    only_in_bronze = df_bronze_business.exceptAll(df_sample)
    diff_count = only_in_sample.count() + only_in_bronze.count()
    data_ok = diff_count == 0

    passed = columns_ok and count_ok and schema_ok and data_ok
    all_passed = all_passed and passed

    print("=" * 60)
    print(f"検証対象: {sample_table}  →  {bronze_table}")
    print("=" * 60)
    print(f"  (1) 件数一致           : sample={sample_count} / bronze={bronze_count} "
          f"-> {'OK' if count_ok else 'NG'}")
    print(f"  (2) 追加された列       : {sorted(added_columns)} "
          f"(期待値: {sorted(METADATA_COLUMNS)}) -> {'OK' if added_columns == set(METADATA_COLUMNS) else 'NG'}")
    print(f"  (3) 欠落・リネーム列   : {sorted(missing_columns) if missing_columns else 'なし'} "
          f"-> {'OK' if not missing_columns else 'NG'}")
    print(f"  (4) データ内容の完全一致 : 差分 {diff_count} 件 -> {'OK' if data_ok else 'NG'}")
    print(f"  (5) 生データ列のスキーマ一致 : -> {'OK' if schema_ok else 'NG'}")

    if not data_ok:
        print("\n  --- sampleにあり bronzeに無い行（差分）---")
        only_in_sample.show(truncate=False)
        print("  --- bronzeにあり sampleに無い行（差分）---")
        only_in_bronze.show(truncate=False)

    if not schema_ok:
        print("\n  --- sample スキーマ ---")
        print(df_sample.schema)
        print("  --- bronze（生データ部分）スキーマ ---")
        print(df_bronze_business.schema)

    print(f"\n  総合判定: {'PASS（生データは変更なし）' if passed else 'FAIL（差分あり、要確認）'}\n")

    results.append((label, passed))


print("=" * 60)
print("Bronze layer 生データ整合性チェック 総合結果")
print("=" * 60)
for label, passed in results:
    print(f"  {label:14s} : {'PASS' if passed else 'FAIL'}")
print("=" * 60)
print(f"最終判定: {'全表 PASS（サンプルデータは変更されずBronze layerに保存されている）' if all_passed else '一部 FAIL（要確認）'}")
