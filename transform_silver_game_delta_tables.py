# Databricks ノートブック用
# Bronze テーブルをクレンジングして Silver レイヤーとして保存する
#
# 処理内容：
#   1. silver_user_master  : registration_dt を DATE 型にキャスト
#   2. silver_gameplay_log : Null 除去 → マスター結合 → 名寄せキー付与
#   3. silver_purchase     : マスター結合 → 名寄せキー付与
#
# 名寄せキー（unified_user_key）について：
#   複数タイトルで同一 user_id が使われるため、
#   タイトルをまたいだ分析では "title_id_user_id" の複合キーで一意識別する

%python
from pyspark.sql import functions as F

# ──────────────────────────────────────────────
# 0. スキーマの作成・切り替え
# ──────────────────────────────────────────────

# スキーマが存在しない場合のみ作成（冪等性を確保）
spark.sql("CREATE DATABASE IF NOT EXISTS interview_prep")
spark.sql("USE interview_prep")

print("スキーマ 'interview_prep' を選択しました\n")


# ──────────────────────────────────────────────
# Bronze テーブルの読み込み
# ──────────────────────────────────────────────

# Bronze 生データを読み込む（クレンジング前の状態）
df_bronze_gameplay = spark.table("interview_prep.bronze_gameplay_log")
df_bronze_purchase = spark.table("interview_prep.bronze_purchase")
df_bronze_user     = spark.table("interview_prep.bronze_user_master")

print(f"Bronze 読み込み完了:")
print(f"  bronze_gameplay_log : {df_bronze_gameplay.count():,} 件")
print(f"  bronze_purchase     : {df_bronze_purchase.count():,} 件")
print(f"  bronze_user_master  : {df_bronze_user.count():,} 件\n")


# ──────────────────────────────────────────────
# 1. silver_user_master
#    クレンジング：registration_dt を文字列から DATE 型に変換
# ──────────────────────────────────────────────

df_silver_user = (
    df_bronze_user
    # Bronze は文字列で保持していた登録日を DATE 型に変換
    .withColumn("registration_dt", F.to_date(F.col("registration_dt")))
)

# 保存
(
    df_silver_user
    .write
    .format("delta")                      # Delta Lake 形式で保存
    .mode("overwrite")                    # 既存テーブルを上書き
    .option("overwriteSchema", "true")    # スキーマ変更も上書き許可
    .saveAsTable("interview_prep.silver_user_master")
)

silver_user_count = spark.table("interview_prep.silver_user_master").count()
print(f"silver_user_master 保存完了: {silver_user_count:,} 件\n")


# ──────────────────────────────────────────────
# 2. silver_gameplay_log
#    Step1 : event_type が Null の行を除去（欠損値クレンジング）
#    Step2 : silver_user_master と LEFT JOIN
#    Step3 : マスター未登録ユーザーを coalesce で「不明」に補完
#    Step4 : タイトルをまたいだ名寄せキー（unified_user_key）を付与
# ──────────────────────────────────────────────

# Step1：event_type が Null の行を除去
df_gameplay_step1 = (
    df_bronze_gameplay
    .filter(F.col("event_type").isNotNull())   # Null 行を除外（データ品質課題 A の対処）
)
null_removed = df_bronze_gameplay.count() - df_gameplay_step1.count()
print(f"[gameplay] Step1 Null 除去: {null_removed} 件削除 → {df_gameplay_step1.count():,} 件")

# Step2：silver_user_master と LEFT JOIN してマスター照合
df_gameplay_step2 = (
    df_gameplay_step1
    .join(
        # JOIN 後にカラム名が衝突しないよう user_id をリネーム
        df_silver_user.select(
            F.col("user_id").alias("master_user_id")
        ),
        on=df_gameplay_step1["user_id"] == F.col("master_user_id"),
        how="left"   # マスター未登録ユーザーも残す（除外しない）
    )
)

# Step3：マスター未登録ユーザーを「不明」で補完
#   coalesce(master_user_id, "不明")
#   → master に存在すれば master_user_id、存在しなければ（NULL）「不明」
df_gameplay_step3 = (
    df_gameplay_step2
    .withColumn(
        "user_id_normalized",
        F.coalesce(F.col("master_user_id"), F.lit("不明"))   # 名寄せ前の正規化済み user_id
    )
    .drop("master_user_id")   # 結合のために使った一時カラムを削除
)
unmatched = df_gameplay_step3.filter(F.col("user_id_normalized") == "不明").count()
print(f"[gameplay] Step3 マスター未登録ユーザー補完: {unmatched} 件 → 'user_id_normalized' = '不明'")

# Step4：タイトルをまたいだ名寄せキーを付与
#   unified_user_key = "title_id_user_id"
#   例）title_001_u_0001 → タイトルごとに同一 user_id が別人の可能性を排除する複合キー
df_silver_gameplay = (
    df_gameplay_step3
    .withColumn(
        "unified_user_key",
        F.concat_ws("_", F.col("title_id"), F.col("user_id"))   # タイトル横断分析用の一意キー
    )
)

# 保存
(
    df_silver_gameplay
    .write
    .format("delta")                      # Delta Lake 形式で保存
    .mode("overwrite")                    # 既存テーブルを上書き
    .option("overwriteSchema", "true")    # スキーマ変更も上書き許可
    .partitionBy("event_date")            # Bronze と同じパーティションキーを維持
    .saveAsTable("interview_prep.silver_gameplay_log")
)

silver_gameplay_count = spark.table("interview_prep.silver_gameplay_log").count()
print(f"silver_gameplay_log 保存完了: {silver_gameplay_count:,} 件\n")


# ──────────────────────────────────────────────
# 3. silver_purchase
#    Step1 : silver_user_master と LEFT JOIN
#    Step2 : マスター未登録ユーザーを coalesce で「不明」に補完
#    Step3 : タイトルをまたいだ名寄せキー（unified_user_key）を付与
# ──────────────────────────────────────────────

# Step1：silver_user_master と LEFT JOIN
df_purchase_step1 = (
    df_bronze_purchase
    .join(
        df_silver_user.select(
            F.col("user_id").alias("master_user_id")
        ),
        on=df_bronze_purchase["user_id"] == F.col("master_user_id"),
        how="left"   # マスター未登録ユーザーも残す
    )
)

# Step2：マスター未登録ユーザーを「不明」で補完
df_purchase_step2 = (
    df_purchase_step1
    .withColumn(
        "user_id_normalized",
        F.coalesce(F.col("master_user_id"), F.lit("不明"))   # 正規化済み user_id
    )
    .drop("master_user_id")
)
unmatched_p = df_purchase_step2.filter(F.col("user_id_normalized") == "不明").count()
print(f"[purchase] Step2 マスター未登録ユーザー補完: {unmatched_p} 件 → 'user_id_normalized' = '不明'")

# Step3：名寄せキーを付与
df_silver_purchase = (
    df_purchase_step2
    .withColumn(
        "unified_user_key",
        F.concat_ws("_", F.col("title_id"), F.col("user_id"))   # タイトル横断分析用の一意キー
    )
)

# 保存
(
    df_silver_purchase
    .write
    .format("delta")                      # Delta Lake 形式で保存
    .mode("overwrite")                    # 既存テーブルを上書き
    .option("overwriteSchema", "true")    # スキーマ変更も上書き許可
    .partitionBy("purchase_date")         # Bronze と同じパーティションキーを維持
    .saveAsTable("interview_prep.silver_purchase")
)

silver_purchase_count = spark.table("interview_prep.silver_purchase").count()
print(f"silver_purchase 保存完了: {silver_purchase_count:,} 件\n")


# ──────────────────────────────────────────────
# 4. 保存結果サマリー
# ──────────────────────────────────────────────

print("=" * 55)
print("=== Silver レイヤー 保存完了サマリー ===")
print("=" * 55)
print(f"  silver_user_master  : {silver_user_count:>6,} 件")
print(f"  silver_gameplay_log : {silver_gameplay_count:>6,} 件  （Null 除去 {null_removed} 件）")
print(f"  silver_purchase     : {silver_purchase_count:>6,} 件")
print("=" * 55)
print("\n追加カラム（Bronze → Silver で新規付与）：")
print("  user_id_normalized : マスター未登録ユーザーを '不明' で補完した user_id")
print("  unified_user_key   : タイトル横断分析用の複合キー（title_id_user_id）")
