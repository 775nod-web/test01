"""PoC & Future Expansion page. Mostly static, labeled content — see
docs/poc-success-criteria.md and docs/free-edition-limitations.md, which
this mirrors. The one live element is a small cross-sell reuse sample."""

from __future__ import annotations

from backend.db import QueryEngine

SYNTHETIC_ELEMENTS = [
    "顧客・口座・カード・アプリ利用・問い合わせ・保有商品・キャンペーンは、すべて固定のランダムシードで生成された"
    "シミュレーションデータです。本デモには実際の銀行データ・顧客データは一切含まれません。",
    "simulated_annual_value（シミュレーション年間価値）と estimated_value_at_risk（推定価値リスク）は"
    "ラベル付きのシミュレーション値であり、実際の財務数値ではありません。",
    "churn_label_90d は任意（Phase 7）のML検証専用のシミュレーション正解ラベルです。"
    "必須のルールベーススコアはこの値を一切参照しません。",
]

MUST_VALIDATE_WITH_BANK_DATA = [
    "8つのシグナル（残高減少・カード利用減少・アプリ利用減少・長期未利用・苦情増加・未解決の問い合わせ・"
    "給与振込停止・保有商品数減少）が、実際のソースシステムで同じ更新頻度で取得・信頼できるか。",
    "docs/risk-scoring.md のポイント配点としきい値（高／中／低）が実際の解約実績と整合するか、"
    "ポートフォリオ・セグメントごとの再調整が必要か。",
    "simulated_annual_value を、財務システムの実際の収益性・取引関係価値の指標に置き換えるべきか。",
    "実際のソースシステムのデータ品質・完全性（欠損・重複・遅延）— Bronze/Silverのクレンジングルールは"
    "実データの複雑さに合わせて見直しが必要。",
    "アクションマッピングで参照しているリテンションチャネル（コールセンター・プッシュ／アプリ・メール）の"
    "実際のキャパシティとコスト。",
]

POC_SUCCESS_METRICS = [
    "リフト: 優先施策対象の継続率・反応率を、現在の一律配信対象と比較し、実キャンペーンで測定する。",
    "要因の安定性: 同じ顧客について主なリスク要因が月をまたいで一貫しているか、ノイズが多いか。",
    "現場での定着: マーケティング／CRM担当者が実際に顧客360と要因説明を使ってアクションを選定するか、"
    "一律配信に戻ってしまわないか。",
    "運用適合性: 推奨アクションが新規ツール導入なしで実際のコールセンター／アプリ／メール運用に"
    "そのまま組み込めるか。",
    "誤検知率: 高リスクと判定された顧客のうち、翌四半期に実際の解約行動が見られない割合。",
]

FREE_EDITION_LIMITATIONS = [
    "実際の銀行ソースシステムへの接続なし。",
    "外部マーケティングツールへの自動連携なし。",
    "リアルタイム／ストリーミング推論なし — バッチ処理のみ。",
    "完全自動化されたNext Best Actionなし — すべての推奨アクションは顧客への連絡前に担当者による確認が必要。",
    "本番グレードのモデルサービングは不要（ルールベーススコアはバッチSQLで計算）。",
    "Free Edition自体の制約: サーバーレスのみのコンピュート、単一の2X-Small SQLウェアハウス、"
    "フェアユース制限、SLAなし、Databricks Appsは24時間非活動で自動停止する場合あり。",
]

CROSS_SELL_REUSE_NOTE = (
    "リテンションで使用しているCustomer 360テーブル（価値・契約期間・保有商品・エンゲージメント・苦情）は、"
    "そのままクロスセル対象の抽出にも応用できます。低リスクでエンゲージメントが高く保有商品数が少ない顧客は、"
    "次に提案すべき商品の候補になり得ます。以下は一つの例示クエリであり、第二のデモではありません"
    "（CLAUDE.mdの固定ストーリーラインを参照）。"
)

# OPTIONAL (Phase 7). Static, pre-computed results from an 8,000-customer
# run — see docs/ml-comparison.md for full methodology, the fairness fix
# (all three approaches evaluated on the identical held-out test set), and
# how to reproduce them. Deliberately NOT a live query: the core app must
# never depend on scikit-learn/pandas being installed, so these numbers
# are baked in here rather than computed per-request.
ML_COMPARISON_NOTE = (
    "任意の技術検証であり、必須デモの一部ではありません。必須のルールベーススコアを、"
    "同一の held-out テストデータ（8,000件のシミュレーション顧客のうち2,400件）で評価した"
    "2つの単純なロジスティック回帰ベースラインと比較しています。churn_label_90d はシミュレーションの"
    "正解ラベルであり、この比較はモデルが生成ロジック自体のパターンを再現できるかを示すものであって、"
    "実際の解約に対する性能を示すものではありません。"
)
ML_COMPARISON_ROWS = [
    {
        "approach": "ルールベース（必須）",
        "precision": 0.799,
        "recall": 0.630,
        "roc_auc": 0.787,
        "note": "アプリが実際に使用しているスコア — 透明性があり、データに学習させたものではない。",
    },
    {
        "approach": "静的属性のみ",
        "precision": 0.421,
        "recall": 0.528,
        "roc_auc": 0.514,
        "note": "年齢層・チャネル・地域・価値区分・契約期間のみ — ほぼランダムと同水準。",
    },
    {
        "approach": "行動データ統合",
        "precision": 0.813,
        "recall": 0.913,
        "roc_auc": 0.900,
        "note": "Customer 360の全行動データ列を使用 — 再現率・AUCともに最高。",
    },
]


def get_poc_summary(engine: QueryEngine) -> dict:
    cross_sell_sample = engine.run("cross_sell_opportunity.sql", limit=10)
    return {
        "synthetic_elements": SYNTHETIC_ELEMENTS,
        "must_validate_with_bank_data": MUST_VALIDATE_WITH_BANK_DATA,
        "poc_success_metrics": POC_SUCCESS_METRICS,
        "free_edition_limitations": FREE_EDITION_LIMITATIONS,
        "cross_sell_reuse_note": CROSS_SELL_REUSE_NOTE,
        "ml_comparison_note": ML_COMPARISON_NOTE,
        "ml_comparison": ML_COMPARISON_ROWS,
        "cross_sell_sample": cross_sell_sample,
    }
