"""
CloudNest サポートチケット テキスト分析スクリプト（Databricks ノートブック用）
======================================================
課題4「サポートチケットのテキストデータを十分に活用できていない」への対応。

このプロトタイプでは、外部モデルサービングエンドポイントを必要としない
軽量なキーワードベースの感情分析・トピック分類を実装し、
  - サポートチケットの「言葉」がヘルススコアの先行指標になり得るか
  - リスクティア別に問い合わせ内容の傾向がどう異なるか
をその場でデモできるようにする。

【本番PoCでのアップグレードパス】
  Databricks の AI Functions（SQL組み込みのLLM呼び出し）を使うと、
  同じことを1行のSQLで、より高精度に、スケーラブルに実行できる：

    SELECT
      ticket_id,
      ai_analyze_sentiment(description)            AS sentiment,          -- 感情分析
      ai_classify(description,
        ARRAY('不具合','料金不満','対応不満','解約検討','利用方法','請求','アップセル','活用相談')
      )                                             AS topic,             -- ゼロショットトピック分類
      ai_query('databricks-meta-llama-3-3-70b-instruct',
        CONCAT('次のサポート問い合わせを一文で要約し、解約リスクを高/中/低で判定して: ', description)
      )                                             AS llm_risk_summary   -- 自由記述の要約・リスク判定
    FROM silver.cloudnest_silver_support_tickets;

  これは Model Serving のFoundation Model APIs経由で動作し、Unity Catalogのガバナンス
  （権限・監査・課金追跡）がそのまま適用される。本ノートブックのキーワードベース実装は
  「オフラインでも動くプロトタイプ」として位置づけ、本番では上記SQLに置き換える想定。

前提：03_silver_transformation.py まで実行済みであること
"""

from pyspark.sql import functions as F
from pyspark.sql.types import StringType

spark.sql("USE gold")

# ──────────────────────────────────────────────
# 0. キーワード辞書（プロトタイプ用の簡易ルールベース分類）
# ──────────────────────────────────────────────

NEGATIVE_KEYWORDS = [
    "遅い", "困っています", "解約", "エラー", "落ちました", "支障", "至急",
    "改善されず", "不安", "困惑", "動かなく", "見合っていない", "検討中",
]
POSITIVE_KEYWORDS = [
    "助かっています", "検討しています", "相談したい", "事例", "導入相談", "見積もり", "使いやすく",
]

TOPIC_KEYWORDS = {
    "不具合": ["エラー", "落ちました", "動かなく", "不具合"],
    "解約検討": ["解約"],
    "パフォーマンス": ["遅い", "読み込み"],
    "料金不満": ["料金", "見合っていない", "他社サービス"],
    "対応不満": ["改善されず", "返信が遅"],
    "アップセル": ["導入相談", "見積もり", "活用事例", "追加ライセンス"],
    "活用相談": ["応用的な使い方", "使いやすく"],
    "請求": ["請求書", "宛先変更"],
    "利用方法": ["方法を教えて", "手順を教えて", "設定について"],
}


def classify_sentiment(text: str) -> str:
    if text is None:
        return "Neutral"
    neg = sum(1 for kw in NEGATIVE_KEYWORDS if kw in text)
    pos = sum(1 for kw in POSITIVE_KEYWORDS if kw in text)
    if neg > pos:
        return "Negative"
    if pos > neg:
        return "Positive"
    return "Neutral"


def classify_topic(text: str) -> str:
    if text is None:
        return "その他"
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return topic
    return "その他"


sentiment_udf = F.udf(classify_sentiment, StringType())
topic_udf = F.udf(classify_topic, StringType())

# ──────────────────────────────────────────────
# 1. サポートチケットにルールベースの感情・トピックを付与
# ──────────────────────────────────────────────

df_tickets = spark.table("silver.cloudnest_silver_support_tickets")

df_tickets_nlp = (
    df_tickets
    .withColumn("predicted_sentiment", sentiment_udf(F.col("description")))
    .withColumn("predicted_topic", topic_udf(F.col("description")))
)

(df_tickets_nlp.write.format("delta").mode("overwrite")
 .option("overwriteSchema", "true").saveAsTable("gold.cloudnest_gold_support_tickets_nlp"))

print(f"=== gold.cloudnest_gold_support_tickets_nlp 保存完了: {df_tickets_nlp.count():,} 件 ===")

# 簡易精度検証：生成時に付与した正解ラベル（_true_sentiment_label）との一致率
# ※ 実データにはこの正解ラベルは存在しない。本プロトタイプの手法妥当性を確認するための検証専用処理。
if "_true_sentiment_label" in df_tickets_nlp.columns:
    accuracy = (
        df_tickets_nlp
        .filter(F.col("_true_sentiment_label").isNotNull())
        .withColumn("match", (F.col("predicted_sentiment") == F.col("_true_sentiment_label")).cast("int"))
        .agg(F.avg("match")).first()[0]
    )
    print(f"\n[検証] キーワードベース感情分析の正解ラベルとの一致率: {accuracy:.1%}")
    print("→ 本番ではai_analyze_sentiment/ai_classify（LLMベース）でさらに高精度化・多言語対応が可能")


# ──────────────────────────────────────────────
# 2. トピック分布（全体）
# ──────────────────────────────────────────────

print("\n=== トピック別チケット件数 ===")
df_tickets_nlp.groupBy("predicted_topic").count().orderBy(F.desc("count")).show(truncate=False)

print("\n=== 感情別チケット件数 ===")
df_tickets_nlp.groupBy("predicted_sentiment").count().orderBy(F.desc("count")).show(truncate=False)


# ──────────────────────────────────────────────
# 3. 顧客単位のチケット感情サマリー（Customer 360 / ヘルススコアとの相関確認用）
# ──────────────────────────────────────────────

df_customer_ticket_sentiment = (
    df_tickets_nlp
    .filter(F.col("created_date") >= F.date_sub(F.current_date(), 90))
    .groupBy("customer_id")
    .agg(
        F.count("*").alias("tickets_last_90d"),
        F.sum(F.when(F.col("predicted_sentiment") == "Negative", 1).otherwise(0)).alias("negative_tickets_last_90d"),
        F.round(F.avg(F.when(F.col("predicted_sentiment") == "Negative", 1).otherwise(0)), 2).alias("negative_ticket_ratio_last_90d"),
    )
)

(df_customer_ticket_sentiment.write.format("delta").mode("overwrite")
 .option("overwriteSchema", "true").saveAsTable("gold.cloudnest_gold_customer_ticket_sentiment"))

print(f"\n=== gold.cloudnest_gold_customer_ticket_sentiment 保存完了: {df_customer_ticket_sentiment.count():,} 件 ===")


# ──────────────────────────────────────────────
# 4. リスクティア別のネガティブチケット比率（ヘルススコアとテキスト分析の相関確認）
#    → 「チケットの言葉」が解約リスクの先行指標になっていることをデモで示す
# ──────────────────────────────────────────────

df_health = spark.table("gold.cloudnest_gold_health_score_latest").select("customer_id", "risk_tier")

print("\n=== リスクティア別 ネガティブチケット比率（テキスト分析とヘルススコアの相関） ===")
(
    df_health.join(df_customer_ticket_sentiment, "customer_id", "left")
    .fillna(0, subset=["tickets_last_90d", "negative_tickets_last_90d", "negative_ticket_ratio_last_90d"])
    .groupBy("risk_tier")
    .agg(
        F.count("*").alias("customer_count"),
        F.round(F.avg("negative_ticket_ratio_last_90d"), 2).alias("avg_negative_ticket_ratio"),
    )
    .orderBy("risk_tier")
    .show(truncate=False)
)

print("\n次のノートブック（07_dashboard_queries.sql）でダッシュボード用SQLを確認してください。")
