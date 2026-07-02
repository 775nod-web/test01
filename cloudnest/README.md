# CloudNest × Databricks プロトタイプ

B2B SaaS企業「CloudNest」向けの Customer 360 / ヘルススコア / 解約リスク可視化 / サポートチケット分析プロトタイプ。
詳細な設計思想は [`docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md)、デモの進め方は [`docs/DEMO_SCRIPT_45MIN.md`](../docs/DEMO_SCRIPT_45MIN.md)、想定Q&Aは [`docs/QA_PREP_15MIN.md`](../docs/QA_PREP_15MIN.md) を参照。

## 実行順序（Databricksノートブックとして上から順に実行）

| # | ファイル | 内容 |
|---|---|---|
| 01 | `01_generate_sample_data.py` | 5ドメインの疑似データ生成（顧客マスター/契約/利用ログ/サポートチケット/請求、350社） |
| 02 | `02_bronze_ingestion.py` | Bronze Deltaテーブルとして保存 |
| 03 | `03_silver_transformation.py` | クレンジング・重複排除・参照整合性検証・週次集計 |
| 04 | `04_gold_customer_360.py` | Customer 360 統合テーブル作成 |
| 05 | `05_health_score_churn_risk.py` | ヘルススコア・解約リスクティア・ARR at risk（週次履歴含む） |
| 06 | `06_support_ticket_nlp_analysis.py` | サポートチケットの感情・トピック分析 |
| 07 | `07_dashboard_queries.sql` | 経営層／CS／DS向けダッシュボードSQL |
| 08 | `08_governance_unity_catalog.sql` | Unity Catalogでのガバナンス設計（本番向け提案・Free Editionでは実行不可） |
| 09 | `09_churn_prediction_baseline_mlflow.py` | MLflow解約予測ベースラインモデル（Phase 2プレビュー） |

動作確認環境：Databricks Free Edition（Unity Catalog不使用・Hiveメタストア）。01〜07・09はそのまま実行可能。08はUnity Catalog有効なワークスペースでの実行を想定した設計ドキュメントとして提示。

## 課題 → 成果物 対応表

| CloudNestの課題 | 対応する成果物 |
|---|---|
| 1. データが分散し顧客状態を一元把握できない | 04 Customer 360 |
| 2. 優先対応すべき顧客の共通指標がない | 05 ヘルススコア／07 B-1 CSM別優先対応リスト |
| 3. 解約判断が担当者の経験に依存している | 05 `top_risk_reason`（スコア内訳の説明可能性） |
| 4. サポートチケットのテキストが未活用 | 06 感情・トピック分析（本番はAI Functions） |
| 5. 経営層が週次でARR at risk等を見たい | 05 週次履歴／07 A-1〜A-4 |
| 6. 解約予測モデルの学習データがない | 04 Customer 360が学習データソースに／09 MLflowベースライン |
| 7. アクセス制御・監査・リネージが必要 | 08 Unity Catalog設計 |

## サンプルデータについて

実際の約3,000社を代表するサンプルとして350社（アクティブ300社＋解約済み50社）を生成している。各顧客に内部的な「ペルソナ」（Champion/Healthy/Watch/AtRisk）を割り当て、利用率トレンド・チケット傾向・支払い状況・契約更新までの日数を相関させることで、ヘルススコアや解約予測モデルが意味のあるシグナルを検知できるようにしている。`_persona_label` `_true_sentiment_label` `_true_topic_label` は検証用の答え合わせラベルであり、実システムには存在しない値のため、本番実装時は参照しないこと。
