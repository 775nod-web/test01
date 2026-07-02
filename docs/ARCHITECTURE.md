# CloudNest × Databricks プロトタイプ アーキテクチャ

## 1. 目的

Customer Success（CS）チーム・経営層・データサイエンス（DS）チームが、**同じ1つの信頼できるデータ基盤**の上で、それぞれの目的（優先対応判断／週次経営指標／解約予測モデル開発）を果たせる状態を、Databricks Lakehouse 上で検証する。

## 2. 全体構成（Medallionアーキテクチャ）

```
[ソースシステム]                  [Bronze]         [Silver]           [Gold]                    [消費層]
──────────────                  ────────         ────────           ──────                    ────────
CRM（顧客・契約）        ─┐
プロダクト利用ログ        ─┤     生データ＋      クレンジング・      Customer 360             CSツール / Genie
サポートデスク            ─┼──▶  取り込み        重複排除・          ヘルススコア／解約リスク  経営ダッシュボード
（Zendesk等）             ─┤     メタデータ      参照整合性検証・     サポートチケットNLP       （週次）
請求システム              ─┘                     週次集計             解約予測ベースライン       DS notebook /
                                                                                                  MLflow / Model Serving
```

本プロトタイプでは 01〜09 のノートブックがこの一連の流れを再現している。

| # | ノートブック | 層 | 内容 |
|---|---|---|---|
| 01 | generate_sample_data.py | (Source) | 5ドメインの疑似データ生成（350社、ペルソナ相関設計） |
| 02 | bronze_ingestion.py | Bronze | 生データ＋取り込みメタデータをDelta化 |
| 03 | silver_transformation.py | Silver | 重複排除・参照整合性・週次集計 |
| 04 | gold_customer_360.py | Gold | 顧客単位の統合ビュー（Customer 360） |
| 05 | health_score_churn_risk.py | Gold | ヘルススコア・解約リスクティア・ARR at risk（週次履歴含む） |
| 06 | support_ticket_nlp_analysis.py | Gold | チケットの感情・トピック分析 |
| 07 | dashboard_queries.sql | Gold→BI | 経営層／CS／DS向けSQL |
| 08 | governance_unity_catalog.sql | 全層 | Unity Catalogでの権限・監査・リネージ設計（本番向け） |
| 09 | churn_prediction_baseline_mlflow.py | Gold→ML | MLflowで追跡するベースライン解約予測モデル |

## 3. 設計判断とその理由

### 3.1 なぜ Lakehouse（1つの基盤）か
CRM・サポートツール・請求システムという別々のSaaSにデータが閉じている限り、CSチームは「今どの顧客が危ないか」を毎回手作業で突き合わせるしかない。Databricks Lakehouseにより、**BI・CS運用・ML学習を同じGoldテーブルから行う**ことで、指標の定義がチーム間でズレる問題（"どのARRが正か"論争）を構造的になくす。

### 3.2 ヘルススコアの設計（課題2・3への対応）
```
health_score = 0.40 × 利用トレンドスコア
             + 0.25 × サポート体験スコア
             + 0.15 × 請求健全性スコア
             + 0.20 × 更新間近リスク補正
```
- 各コンポーネントを保持し、`top_risk_reason` として言語化することで、CSMの経験則に依存せず「なぜこの顧客が危ないのか」をデータで説明できるようにした。
- 「契約更新90日以内」の顧客は利用トレンドの悪化を二重に反映する設計とし、CloudNestが最も課題としていた「更新前の利用率低下の見落とし」を直接検知する。

### 3.3 週次スナップショットとして履歴化（課題5への対応）
ヘルススコアは「今のスナップショット」だけでなく、Silverテーブルから任意時点の特徴量を再計算できる関数を用意し、直近8週分を履歴テーブル化した。本番では Databricks Workflows で毎週ジョブ実行し、ARR at riskの週次トレンドを経営ダッシュボードで自動更新する。

### 3.4 サポートチケットNLP（課題4への対応）
プロトタイプではモデルサービングを使わないキーワードベースの感情・トピック分類で「テキストが解約の先行指標になり得るか」を素早く検証。本番では Databricks AI Functions（`ai_analyze_sentiment` / `ai_classify` / `ai_query`）に置き換えることで、SQL数行のままLLM品質の分析へ移行できる（コードは06ノートブック内にサンプル記載）。

### 3.5 解約予測のPhase 2プレビュー（課題6への対応）
「信頼できるCustomer 360がないためモデルが作れない」という課題に対し、本プロトタイプがまさにその土台になることを、実際にMLflowでベースラインモデル（GBTClassifier）を学習させて示す。学習データは**時点整合性（point-in-time correctness）**を担保し、解約が起きる30日前に予測できるかを検証する設計とした。

### 3.6 ガバナンス（課題7への対応）
Unity Catalogを前提に、行レベルセキュリティ（CSMは自分の担当顧客のみ）・列マスキング（ARRの丸め表示）・タグベースのデータ分類・監査ログ・自動リネージを設計（08ノートブック）。ライブデモ環境（Free Edition）ではUnity Catalog機能が使えないため、これは「提案として提示」する形を取っている。

## 4. 本番化ロードマップ（概要。詳細は QA_PREP_15MIN.md）

| フェーズ | 内容 |
|---|---|
| Ingestion | LakeFlow Connect / Partner Connect で CRM・Zendesk・Stripe等と接続。プロダクトイベントは Structured Streaming / Auto Loader でほぼリアルタイム取り込み |
| Transformation | Bronze→Silver→Gold を Lakeflow Declarative Pipelines（宣言的品質エクスペクテーション）で実装 |
| Orchestration | Databricks Workflows で日次/週次ジョブ化。失敗時アラートはSlack/Email連携 |
| Governance | Unity Catalog（08の設計を全面適用）。system.access.audit で監査、Lakehouse Monitoringでドリフト検知 |
| Consumption | AI/BI Genie・Dashboardsで自然言語による経営層セルフサービス分析、CSツールへのAPI/Reverse ETL連携 |
| ML | Feature Store・MLflow Model Registry・Model Servingで解約予測を本番運用、CSMフィードバックで継続学習 |
| CI/CD | Databricks Asset Bundles（DAB）でノートブック・ジョブ・権限をコード管理し環境間デプロイ |
