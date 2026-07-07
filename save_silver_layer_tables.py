"""
小売メダリオンアーキテクチャ Silverレイヤー保存スクリプト
（Databricks Free Edition Notebook 実行想定）

【重要】本ファイルはDatabricksノートブックの「1つのセル」にまとめて
貼り付けて実行してください。処理全体を1つの関数にまとめているため、
関数定義の一部だけを別セルにコピーする、あるいは関数の呼び出し部分
（末尾の save_silver_layer_tables()）を書き忘れると、
NameError: name 'df_bronze_stores' is not defined のようなエラーになります。

前提：save_bronze_layer_tables.py を同セッションで実行済みで、
      bronzeスキーマに以下4表が保存されていること
        - bronze.store_master
        - bronze.product_master
        - bronze.member_master
        - bronze.pos_transactions

本スクリプトは bronze スキーマのデータに対し、Knowledge baseに定義された
品質課題を以下の方針で改善し、silver スキーマへ保存する。

  - transaction idの重複            → transaction_id単位で重複除去
  - transaction timestampの表記揺れ → 想定される9パターンの書式を
                                       try_to_timestamp で解析しTimestampTypeに標準化
                                       （生データはtransaction_timestamp_rawとして残す）
  - product idがproduct masterに存在しない → 無効レコードとしてSilverの
                                       正データから除外（rejectedテーブルへ）
  - store idがstore masterに存在しない     → 同上
  - quantityが0または負の値                → 同上
  - unit priceがnullまたは負               → 同上
  - customer idがnullの取引               → 非会員取引として許容し除外しない
                                       （業務上あり得るパターンのため）
  - product categoryがnullの商品           → 「未分類」で補完（除外しない）

除外した無効レコードは silver.pos_transactions_rejected に理由付きで保存し、
データが失われず追跡できるようにする（Gold層のデータ品質サマリの元データ）。
"""

from pyspark.sql import functions as F


def save_silver_layer_tables():
    """bronzeスキーマのデータを品質改善し、silverスキーマへ保存する。"""

    spark.sql("CREATE SCHEMA IF NOT EXISTS silver")
    print("スキーマ 'silver' を確認/作成しました")

    # ──────────────────────────────────────────────
    # 1. Bronzeレイヤーの読み込み
    # ──────────────────────────────────────────────

    df_bronze_stores   = spark.table("bronze.store_master")
    df_bronze_products = spark.table("bronze.product_master")
    df_bronze_members   = spark.table("bronze.member_master")
    df_bronze_pos       = spark.table("bronze.pos_transactions")

    # ──────────────────────────────────────────────
    # 2. store_master / member_master：コンフォームドコピー
    #    （品質課題が無いため変換は不要。Silverの単一参照層として保持する）
    # ──────────────────────────────────────────────

    df_silver_stores  = df_bronze_stores
    df_silver_members = df_bronze_members

    # ──────────────────────────────────────────────
    # 3. product_master：product_categoryのnullを「未分類」で補完
    # ──────────────────────────────────────────────

    df_silver_products = df_bronze_products.withColumn(
        "product_category",
        F.coalesce(F.col("product_category"), F.lit("未分類")),
    )

    # ──────────────────────────────────────────────
    # 4. pos_transactions：品質改善
    # ──────────────────────────────────────────────

    # --- 4-1. 取引ID重複除去 ---
    df_pos_dedup = df_bronze_pos.dropDuplicates(["transaction_id"])

    # --- 4-2. timestamp標準化（表記揺れの吸収） ---
    # Bronzeに混在する書式（正常書式 + 意図的に含めた8種類の表記揺れ）を
    # 想定した書式リスト。try_to_timestampはパース失敗時にエラーではなくnullを返す。
    TIMESTAMP_FORMATS = [
        "yyyy-MM-dd HH:mm:ss",             # 正常書式
        "yyyy/MM/dd HH:mm",                # スラッシュ区切り・秒なし
        "dd-MM-yyyy HH:mm:ss",             # 日-月-年順
        "yyyy-MM-dd'T'HH:mm:ssXXX",        # ISO8601 + オフセット（+09:00）
        "yyyy-MM-dd HH:mm:ss 'JST'",       # タイムゾーン名（JST）付き
        "yyyyMMddHHmmss",                  # 区切りなし数値羅列
        "yyyy-MM-dd'T'HH:mm:ss'Z'",        # UTC表記（Zサフィックス）
        "MM/dd/yyyy hh:mm a",              # 米国式12時間表記
        "yyyy-MM-dd HH:mm:ss.SSSSSS",      # マイクロ秒付き
    ]

    parsed_timestamp = F.coalesce(*[
        F.expr(f"try_to_timestamp(transaction_timestamp, '{fmt}')")
        for fmt in TIMESTAMP_FORMATS
    ])

    df_pos_std = (
        df_pos_dedup
        .withColumn("transaction_timestamp_raw", F.col("transaction_timestamp"))  # 生データを保持
        .withColumn("transaction_timestamp", parsed_timestamp)                     # 標準化後の値で上書き
    )

    # --- 4-3. マスター整合性チェック用の有効ID一覧 ---
    valid_store_ids   = [r.store_id for r in df_silver_stores.select("store_id").collect()]
    valid_product_ids = [r.product_id for r in df_silver_products.select("product_id").collect()]

    # --- 4-4. 有効性判定条件 ---
    is_valid_store     = F.col("store_id").isin(valid_store_ids)
    is_valid_product    = F.col("product_id").isin(valid_product_ids)
    is_valid_quantity   = F.col("quantity").isNotNull() & (F.col("quantity") > 0)
    is_valid_price      = F.col("unit_price").isNotNull() & (F.col("unit_price") > 0)
    is_valid_timestamp  = F.col("transaction_timestamp").isNotNull()

    is_valid_all = is_valid_store & is_valid_product & is_valid_quantity & is_valid_price & is_valid_timestamp
    # ※ customer_idのnullは非会員取引として許容するため、有効性判定には含めない

    # --- 4-5. 却下理由の付与（複数該当する場合も配列で保持、array_compactでnull要素を除去） ---
    rejection_reasons = F.array_compact(
        F.array(
            F.when(~is_valid_store, F.lit("store_id不整合")),
            F.when(~is_valid_product, F.lit("product_id不整合")),
            F.when(~is_valid_quantity, F.lit("数量異常")),
            F.when(~is_valid_price, F.lit("単価異常")),
            F.when(~is_valid_timestamp, F.lit("timestamp解析失敗")),
        )
    )

    df_pos_flagged = df_pos_std.withColumn("rejection_reasons", rejection_reasons)

    # --- 4-6. 正データ／却下データへ分離 ---
    df_silver_pos = df_pos_flagged.filter(is_valid_all).drop("rejection_reasons")
    df_silver_pos_rejected = df_pos_flagged.filter(~is_valid_all)

    # ──────────────────────────────────────────────
    # 5. silverスキーマへの保存
    # ──────────────────────────────────────────────

    (df_silver_stores.write.format("delta").mode("overwrite")
     .option("overwriteSchema", "true").saveAsTable("silver.store_master"))
    (df_silver_products.write.format("delta").mode("overwrite")
     .option("overwriteSchema", "true").saveAsTable("silver.product_master"))
    (df_silver_members.write.format("delta").mode("overwrite")
     .option("overwriteSchema", "true").saveAsTable("silver.member_master"))
    (df_silver_pos.write.format("delta").mode("overwrite")
     .option("overwriteSchema", "true").saveAsTable("silver.pos_transactions"))
    (df_silver_pos_rejected.write.format("delta").mode("overwrite")
     .option("overwriteSchema", "true").saveAsTable("silver.pos_transactions_rejected"))

    print("\n=== Silverレイヤー保存完了 ===")
    print(f"  silver.store_master              : {spark.table('silver.store_master').count():>4,} 件")
    print(f"  silver.product_master             : {spark.table('silver.product_master').count():>4,} 件")
    print(f"  silver.member_master              : {spark.table('silver.member_master').count():>4,} 件")
    print(f"  silver.pos_transactions           : {spark.table('silver.pos_transactions').count():>4,} 件（正データ）")
    print(f"  silver.pos_transactions_rejected  : {spark.table('silver.pos_transactions_rejected').count():>4,} 件（却下データ）")
    print(f"  (参考) bronze.pos_transactions    : {spark.table('bronze.pos_transactions').count():>4,} 件（加工前）")


# スクリプト全体を1回の呼び出しで実行する（NameError対策として関数化している）
save_silver_layer_tables()
