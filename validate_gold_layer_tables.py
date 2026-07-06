# Databricks ノートブック用
# Gold層 空テーブルの作成結果を確認するスクリプト
#
# 前提：create_gold_layer_tables.py を同セッションで実行済みであること
#
# 表示内容：
#   1. gold スキーマに存在するテーブル一覧
#   2. 各表のスキーマ定義（列名・型・nullable）
#   3. 各表の件数（作成直後は0件であることの確認）

print("=" * 60)
print("Cloudbox Gold層 テーブル作成結果検証レポート")
print("=" * 60)

GOLD_TABLES = [
    "gold_daily_kpi",
    "gold_at_risk_users",
    "gold_data_quality_summary",
    "gold_user_ml_features",
]

# ──────────────────────────────────────────────
# 1. gold スキーマのテーブル一覧
# ──────────────────────────────────────────────

print("\n--- gold スキーマのテーブル一覧 ---")
spark.sql("SHOW TABLES IN gold").show(truncate=False)


# ──────────────────────────────────────────────
# 2・3. 各表のスキーマ定義と件数
# ──────────────────────────────────────────────

for table_name in GOLD_TABLES:
    full_name = f"gold.{table_name}"
    print("\n" + "-" * 60)
    print(f"--- {full_name} ---")

    df = spark.table(full_name)

    print("[スキーマ定義]")
    df.printSchema()

    print("[DESCRIBE TABLE]")
    spark.sql(f"DESCRIBE TABLE {full_name}").show(truncate=False)

    row_count = df.count()
    print(f"[件数] {row_count} 件（空テーブルのため0件であることを確認）")

print("\n" + "=" * 60)
print("=== Gold層 空テーブルの検証完了 ===")
print("=" * 60)
