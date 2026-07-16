# 顧客休眠予兆・次アクション支援デモ

## 1. このリポジトリの目的

Databricks Free EditionとDatabricks Appsを使い、次の一連の業務を日本語で実演するデモを構築します。

1. ECとQR決済・カードのデータを顧客単位で統合する
2. グループ全体の顧客360を表示する
3. 顧客の休眠リスクを予測する
4. 顧客データ、予測結果、社内ナレッジから次アクション候補を提示する
5. 顧客維持担当者が承認、修正、見送りを行う
6. 判断と施策結果を次の分析・モデル・施策改善へ戻す

デモの中心となる問いは一つです。

> この顧客へ今対応すべきか。対応するなら、どのアクションが妥当か。

## 2. 現在の実装状況（Phase 1〜4）

### Phase 1（土台）
- React + TypeScript + Vite のフロントエンド骨格（1画面、日本語ベースレイアウト）
- FastAPI + Uvicorn のPythonバックエンド骨格
- `/api/health`、`/api/metadata` の実装
- Databricks接続未設定でも起動する `demo` モードの設定層
- **デプロイ前ビルド方式**：Reactは事前にProduction Buildし、`frontend/dist` をPythonが配信する。Databricks Apps（`APP_ENV=production`）ではビルド成果物が無い場合に起動を失敗させ、UIが欠落したまま正常起動したように見せない
- デプロイ前準備を一括実行する `scripts/prepare_deploy.sh`
- Databricks Apps向け `app.yaml`
- ホスト・ポート解決、データモード判定、起動モード判定の単体テスト

### Phase 2（Layer 1: データ基盤 / Layer 2: 予測型ML）
- 固定シードで再現可能な合成データ生成（EC・QR決済・カード・銀行・過去施策・問い合わせ履歴）
- `customer_id` で統合した顧客360（`scripts/prepare_customer360.py` → `artifacts/customer360.json`）
- 単純で説明可能な休眠予測モデル（ロジスティック回帰）と、事前計算済み予測（`scripts/train_model.py` → `artifacts/predictions.json`）
- `GET /api/customers`、`GET /api/customers/{customer_id}` の実装（顧客360と予測結果をcustomer_idで結合して返す）
- Databricks利用時とデモデータ利用時の差し替え境界（`backend/services/data_source.py`）
- データ品質の自動チェック（生成スクリプト内 + `backend/tests/test_data_quality.py`）
- 左「本日の優先顧客」リスト、中央「顧客360」利用推移グラフ・「休眠リスク」表示のUI実装

### Phase 3（Layer 3: GenAI・RAG相当 / Layer 4: 判断・フィードバック）
- 社内ナレッジ文書6件（過去施策の説明・サービス情報・顧客対応方針）と、顧客360・予測を統合するコンテキスト作成（`backend/services/recommendation_context.py`）
- 実LLMエンドポイント → 事前生成済みLLM回答 → ルールベース生成の3段フォールバック（`backend/services/recommendation_service.py`）。実LLM呼び出しにはタイムアウト・再試行上限・出力スキーマ検証（ハルシネーション参照元の拒否を含む）を実装
- `GET /api/customers/{customer_id}/recommendation`、`POST /api/customers/{customer_id}/decision`、`GET /api/feedback-summary` の実装
- 判断（承認・修正・見送り）をファイルへ保存し、Databricks側の保存先が設定されている場合に差し替えられる設計（`backend/services/decision_store.py`）
- 右「次のアクション」パネル（要約・候補・理由・注意事項・参照元・生成方式・承認/修正/見送り）と、下部「フィードバック概要」のUI実装

### Phase 4（UI完成・デモストーリー・データ整合性の仕上げ）
- 画面各所の見出しに①〜⑥の番号を付け、デモの流れ（優先顧客選定→顧客360→休眠リスク→次アクション→承認/修正/見送り→フィードバック概要）を視覚的に示す
- ヘッダーにデータモード・モデルモード・最終更新を常時表示（生成方式は顧客ごとの性質上、次のアクションパネル内に表示）
- 技術詳細・本番化境界を折りたたみ式の「デモ構成／本番化時に追加する事項」へ隔離し、通常時は非表示にする
- APIエラー・ネットワーク障害時も日本語メッセージを表示し、各パネルを`ErrorBoundary`で分離することで、一部の表示エラーが画面全体をクラッシュさせないようにする
- ルールベース生成が、過去に同じ施策種別で「反応なし」だった場合にその旨を注意事項へ明記し、優先度を下げるよう改善（推奨とフィードバック履歴の矛盾を防止）
- 高・中・低リスクの代表顧客についてデータ・予測・推奨の整合性を確認（本README 18節参照）

## 3. 技術構成

### フロントエンド
- TypeScript
- React
- Vite
- 日本語UI

### バックエンド
- Python
- FastAPI
- Uvicorn
- Reactビルド成果物の配信
- REST API

### 実行先
- Databricks Apps
- Databricks Free Edition

Node.jsはReactのビルドにのみ使用します。Databricks Apps起動時にNode.js/npmは実行しません（デプロイ前ビルド方式）。Expressをバックエンドには使用しません。Streamlitも使用しません。

## 4. ディレクトリ構成（現状）

```text
.
├── CLAUDE.md
├── DEMO_SPEC.md
├── README.md
├── app.yaml
├── requirements.txt
├── .gitignore
├── scripts/
│   ├── prepare_deploy.sh              # デプロイ前ビルド・テストの一括実行スクリプト
│   ├── requirements-scripts.txt        # 合成データ生成・モデル学習専用の依存関係（backendには不要）
│   ├── generate_demo_data.py           # 固定シードの合成データ生成 → data/
│   ├── prepare_customer360.py          # data/ → artifacts/customer360.json（顧客360統合）
│   ├── train_model.py                  # artifacts/customer360.json → artifacts/predictions.json, model_metadata.json
│   └── generate_pregenerated_recommendations.py  # → artifacts/pre_generated_recommendations.json
├── data/                                # 合成データ（生データ）。コミット対象
│   ├── customers.csv
│   ├── ec_transactions.csv
│   ├── payment_transactions.csv
│   ├── bank_transactions.csv
│   ├── campaigns.csv
│   ├── customer_support.json
│   ├── generation_meta.json
│   └── knowledge/
│       └── knowledge_base.json         # 過去施策の説明・サービス情報・顧客対応方針（計6件）
├── artifacts/                           # 統合済みデータ・事前計算済み結果。コミット対象（フォールバック用）
│   ├── customer360.json
│   ├── predictions.json
│   ├── model_metadata.json
│   └── pre_generated_recommendations.json
├── runtime/                              # 判断保存など実行時state。Git管理外（.gitignore）
│   └── decisions.json                    # POST /api/customers/{id}/decision で生成される
├── backend/
│   ├── main.py                         # FastAPIエントリーポイント（起動モード判定・Reactビルドの配信を含む）
│   ├── config.py                        # ホスト・ポート・データモード・起動モード・LLM接続解決ロジック
│   ├── api/
│   │   └── routes.py                    # /api/health 〜 /api/feedback-summary 全エンドポイント
│   ├── models/
│   │   └── schemas.py                   # APIレスポンスのPydanticスキーマ
│   ├── services/
│   │   ├── data_source.py               # Databricks/demoデータ取得の差し替え境界
│   │   ├── customer_service.py          # 顧客360と予測の結合ロジック
│   │   ├── knowledge_base.py            # 社内ナレッジ文書の読み込み
│   │   ├── recommendation_context.py    # 顧客360＋予測＋ナレッジのコンテキスト作成
│   │   ├── llm_client.py                # 実LLM呼び出し（タイムアウト・再試行・出力検証）
│   │   ├── pre_generated_store.py       # 事前生成済み回答フィクスチャの読み込み
│   │   ├── rule_based_generator.py      # 決定論的ルールベース生成（最終フォールバック）
│   │   ├── recommendation_service.py    # llm→pre_generated→rule_basedの切り替え
│   │   ├── decision_store.py            # 判断保存（ファイル／Databricks差し替え境界）
│   │   ├── decision_service.py          # 判断保存の入力検証・組み立て
│   │   └── feedback_service.py          # フィードバック概要の集計
│   └── tests/
│       ├── test_config.py
│       ├── test_api.py
│       ├── test_deploy_modes.py         # development/productionモードの起動挙動テスト
│       ├── test_customers_api.py        # /api/customers, /api/customers/{id} の疎通テスト
│       ├── test_data_source.py          # Databricks/demo差し替え境界のテスト
│       ├── test_data_quality.py         # DEMO_SPECのデータ品質要件の自動チェック
│       ├── test_llm_client.py           # LLM呼び出しのタイムアウト・再試行・出力検証テスト
│       ├── test_recommendation_service.py  # llm→pre_generated→rule_based切り替えテスト
│       ├── test_recommendation_api.py   # /api/customers/{id}/recommendation の疎通テスト
│       └── test_decision_and_feedback.py   # 判断保存・フィードバック概要のテスト
├── frontend/
│   ├── package.json
│   ├── package-lock.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── index.html
│   ├── dist/                           # npm run build で生成（Git管理外）
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── App.css
│       ├── types.ts
│       ├── api/client.ts
│       ├── components/
│       │   ├── CustomerListPanel.tsx
│       │   ├── Customer360Panel.tsx
│       │   ├── RiskPanel.tsx
│       │   ├── UsageTrendChart.tsx
│       │   ├── RiskBadge.tsx
│       │   ├── RecommendationPanel.tsx  # 次のアクション（要約・候補・承認/修正/見送り）
│       │   └── FeedbackSummaryPanel.tsx # フィードバック概要
│       └── styles/
│           ├── tokens.css
│           └── global.css
├── generate_ecommerce_sample_data.py   # Databricksノートブック用（Phase 1以前から存在）
└── save_bronze_delta_tables.py         # Databricksノートブック用（Phase 1以前から存在）
```

## 5. データ生成・顧客360・モデル学習パイプライン（Layer 1 / Layer 2）

`data/` と `artifacts/` はどちらも**コミット対象**です。「アプリ停止後に再起動してもデモできるよう、必要データと事前計算結果をリポジトリに含める」というDatabricks Free Edition向けの方針（本ファイル参照元READMEテンプレート）に従い、生成済みの合成データと予測結果をフォールバック用としてリポジトリへ保存しています。

### 実行順序

```bash
python3 -m venv .venv-scripts
source .venv-scripts/bin/activate
pip install -r requirements.txt -r scripts/requirements-scripts.txt

python scripts/generate_demo_data.py       # data/ に合成データを生成
python scripts/prepare_customer360.py      # artifacts/customer360.json を生成（顧客360統合）
python scripts/train_model.py              # artifacts/predictions.json, model_metadata.json を生成
```

`scripts/requirements-scripts.txt`（scikit-learn, numpy）は**この3スクリプトの実行時のみ**必要です。backend（Databricks Apps上で実行される本番プロセス）は `artifacts/` 配下の生成済みJSONを読むだけなので、`requirements.txt`（backendの依存関係）にはscikit-learn等を含めていません。

### Layer 1: 合成データと顧客360

- `scripts/generate_demo_data.py` は固定シード（`SEED = 42`）と固定の基準日（`AS_OF_DATE = 2026-07-16`）を使い、60人分の匿名顧客について、EC・QR決済・カード（必須データソース）、ネット銀行・過去施策・問い合わせ履歴（任意データソース）の取引明細をランダムだが常識的な範囲で生成する。
- 生成するのは取引明細のみで、月次集計・最終利用日・利用サービス数などの派生値は一切含めない。これにより「最終利用日と利用履歴が矛盾しない」というデータ品質要件を、二重管理ではなく構造的に満たしている（`scripts/prepare_customer360.py` が生データから毎回計算し直す）。
- `scripts/prepare_customer360.py` は `customer_id` をキーに、直近4期間（各30日）のEC・QR決済・カード・銀行の利用額・頻度・最終利用日・前期比、利用サービス数（現在・前期）、QR・カード合算の利用推移、過去施策と反応、問い合わせ概要を1顧客1レコードへ統合し、`artifacts/customer360.json` に書き出す。
- 同スクリプトは書き出し前に構造的なデータ品質チェック（負の金額、全期間ゼロ、customer_id重複、未来日付の取引）を実行し、違反があれば非0終了コードで処理を止める（不正なデータをartifacts/へ出力しない）。

### Layer 2: 休眠リスク予測

- **ラベル生成ルール**（`scripts/train_model.py` 内に実装）：実際の解約フラグは存在しない合成データのため、以下の重み付け合成スコアを「経済的な休眠傾向」の目安として定義し、これを成功確率とみなしたベルヌーイ試行で教師ラベルを生成する。

  ```text
  dormancy_score =
        0.25 × EC利用額の累積低下（最初期間→直近期間、-50%以上で成分1.0に飽和）
      + 0.30 × QR・カード合算利用額の累積低下（-60%以上で成分1.0に飽和）
      + 0.25 × 利用サービス数の減少（2サービス減で成分1.0に飽和）
      + 0.20 × 直近利用からの経過日数（90日以上で成分1.0に飽和）
      - 0.07 × 直近施策への反応が「反応あり」の場合
      + 0.03 × 「退会・解約に関する相談」の問い合わせがある場合
  ```

  ラベル自体はロジスティック回帰の入力特徴量には含めず、上記スコアの元になった生の特徴量（EC/QR・カードの累積低下率、サービス数減少、経過日数、施策反応、問い合わせ有無）から再構成させることで、単純な恒等学習にならないようにしている。
- **モデル**：scikit-learnの `LogisticRegression`（標準化した数値特徴量、`class_weight="balanced"`）。60件中45件で学習し、15件のホールドアウトで評価する。評価値（accuracy / precision / recall / roc_auc）は `artifacts/model_metadata.json` に記録するが、**小規模な合成データ上の参考値であり、本番精度を示すものではない**（画面の主役にもしない）。
- **リスク帯**：休眠確率 0.66以上を「高」、0.34未満を「低」、その間を「中」とする。生成時点の実測分布は高16人・中9人・低35人で、3帯すべてが常識的な人数で存在することを自動チェックしている。
- **理由生成**：`compute_dormancy_score` と同じ重みで各要因の寄与度を計算し、寄与が大きい順に最大3件を表示用の日本語文へ変換する（例：「ECの直近期間の購入額が前期比-29%低下しています」）。これにより、画面のグラフの数値と表示される理由が食い違わないようにしている。低リスク顧客など減少要因がない場合は、増加傾向や施策への反応など安定・良好を示す理由で補う。
- **フォールバック**：モデル学習・推論はこのスクリプトの実行時（オフライン）にのみ行い、backendは常に事前計算済みの `artifacts/predictions.json` を読むだけなので、`model_mode` はAPI上つねに `precomputed` として返す（`trained` は将来Databricksモデルサービング等に接続した場合の値として予約している）。

### 再現性とデータ品質

- `generate_demo_data.py` は同一シード・同一コードであれば何度実行しても同一の `data/` を生成する（wall-clockに依存する値を持たない）。実行結果は差分なしで確認済み。
- `prepare_customer360.py` と `train_model.py` の出力も、タイムスタンプ系フィールド（`generated_at`, `trained_at`, `inference_at`, `checked_at`）を除けば再実行時に完全一致することを確認済み。
- DEMO_SPEC.mdの「データ品質の必須検証」は、生成スクリプト内の即時チェック（違反時は非0終了）と `backend/tests/test_data_quality.py` の両方でカバーしている（本README 18節「データ品質」参照）。

## 6. 推奨アクション生成パイプライン（Layer 3 / GenAI・RAG相当）

顧客360・休眠予測・社内ナレッジを統合し、次アクション候補を生成する。実行優先順位は次のとおり。

```text
1. 設定済みの実LLMエンドポイント（backend/services/llm_client.py）
2. 事前生成済みLLM回答（artifacts/pre_generated_recommendations.json）
3. 決定論的なルールベース生成（backend/services/rule_based_generator.py、常に成功する）
```

`backend/services/recommendation_service.py` がこの優先順位で順に試行し、いずれかが成功した時点で結果を返す。ルールベース生成は入力データのみから決定論的に組み立てるため、原理上必ず成功し、Step 1〜6のデモフローがLLM未設定・未接続でも必ず完走できる。

### 社内ナレッジ文書（`data/knowledge/knowledge_base.json`）

過去施策の説明4件、サービス情報1件、顧客対応方針1件の計6件を、`doc_id` / `title` / `category` / `updated_at` / `body` を持つJSONとして保持する。件数が少ないため事前フィルタリングはせず、全件を生成方式へ候補として渡し、実際に根拠として使った文書のみを「参照元」としてAPI・UIへ返す（`backend/services/knowledge_base.py`）。

### コンテキスト構築（`backend/services/recommendation_context.py`）

`customer_id` から顧客360（`artifacts/customer360.json`）・休眠予測（`artifacts/predictions.json`）・社内ナレッジ全件を1つのコンテキストへ統合する。LLM・事前生成済み回答・ルールベースのいずれの生成方式も、同じコンテキストを入力として受け取ることで、方式が変わっても参照データの一貫性を保つ。

### 実LLM呼び出し（`backend/services/llm_client.py`）

- 接続情報は環境変数からのみ取得し、コードへ直接記載しない。

  ```text
  LLM_ENDPOINT_URL       LLMエンドポイントのURL（未設定なら実LLMは使わない）
  LLM_API_KEY            認証情報（Bearerトークンとして送信）
  LLM_MODEL              任意。モデル識別子（未設定でも動作する）
  LLM_TIMEOUT_SECONDS    任意。既定8秒
  LLM_MAX_RETRIES        任意。既定1回（＝最大2回試行）
  ```

- `LLM_ENDPOINT_URL` と `LLM_API_KEY` が両方設定されている場合のみ実LLMを試行する（`backend/config.py` の `resolve_llm_config()`）。
- リクエストはOpenAI互換のchat completions形式（`messages` に system/user、レスポンスは `choices[0].message.content` がJSON文字列）を想定している。Databricks Model Serving等、実際に利用するエンドポイントの形式に合わせて `_call_endpoint` を調整する必要がある（本README 16節「実装上の仮定」参照）。
- 出力は必ずスキーマ検証する：`summary`（1〜400字）、`actions`（1〜3件、各titleとreason）、`cautions`（文字列配列）、`references`（コンテキストで渡した`doc_id`のみ許可。それ以外を含む出力＝ハルシネーションとして拒否する）。
- 通信エラー・タイムアウトは最大 `LLM_MAX_RETRIES` 回まで再試行する。出力形式の不正は再試行しても解決しないため、検証失敗時は即座に打ち切る。
- 失敗時は例外（`LLMRequestError` / `LLMOutputInvalidError`）を送出するのみで、リクエストヘッダー・レスポンス本文・秘密情報はログへ出力しない（例外の型名のみを記録する）。呼び出し元（`recommendation_service`）が捕捉し、次の方式へフォールバックする。

### 事前生成済みLLM回答（`artifacts/pre_generated_recommendations.json`）

高・中・低リスクから2件ずつ、計6顧客（C059, C017, C015, C045, C010, C031）分の回答を `scripts/generate_pregenerated_recommendations.py` で保存している。本文は開発時にLLM（Claude Code）が実際の顧客360・予測結果・社内ナレッジを踏まえて作成したものであり、「事前生成済みLLM回答」という表示に偽りはない。対象外の54顧客は自動的にルールベース生成へフォールバックする。

### ルールベース生成（`backend/services/rule_based_generator.py`）

- 候補アクションはDEMO_SPEC.mdの5種類（EC再利用の案内／QR決済の利用メリット案内／カード利用特典の案内／複数サービスをまたぐ軽量なポイント施策／施策を行わず経過観察）のみを使う。
- EC・QR決済・カードそれぞれの前期比低下、利用サービス数の減少を根拠に対象アクションを選び、寄与度順に**最大2件**に絞る。残り1枠は必ず「施策を行わず経過観察」に確保し、高リスクでも一律に施策を実施するロジックにしない。
- 直近30日以内に施策を配信済みの顧客には「効果を見極める期間として経過観察も選択肢」という理由を、減少要因が無い顧客には「安定しているため経過観察」という理由を出し分ける。
- 理由文は `compute_dormancy_score` 相当の重み付けで算出した寄与度順に並べるため、休眠リスクのグラフ・理由と矛盾しない。
- 参照元は実際に選んだアクションに対応する社内ナレッジ文書のみを返す（例：QR決済の施策を選んだ場合は `kb-qr-incentive` のみ）。

### 生成方式の表示

APIレスポンスの `generation_mode`（内部値）と `generation_mode_label`（表示名）は必ず一致する。

| generation_mode | generation_mode_label |
| --- | --- |
| `llm` | LLM生成 |
| `pre_generated` | 事前生成済みLLM回答 |
| `rule_based` | デモ用ルールベース生成 |

ルールベース生成を「LLM実行済み」「生成AI実行済み」と表示することはない。

## 7. ローカル開発

Phase 1〜2の開発中は、フロントエンドをビルドせずにAPIとVite開発サーバーを別々に起動して作業できます（development モード、既定）。

### バックエンド（Python）

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windowsは .venv\Scripts\activate
pip install -r requirements.txt

# テスト実行
python -m pytest backend/tests -v

# 開発起動（APP_ENV未設定＝developmentモード。frontend/dist が無くてもAPIのみで起動する）
python -m backend.main
```

### フロントエンド（Node.js / npm）

```bash
cd frontend
npm install

# 開発サーバー（Viteが /api を http://127.0.0.1:8000 へプロキシ）
npm run dev

# 型チェックのみ
npm run typecheck
```

developmentモードでは `frontend/dist` の有無にかかわらずPython APIが起動するため、`npm run dev` の開発サーバーと `python -m backend.main` を並行起動して開発できます。

## 8. デプロイ前ビルド（Production Build）

このデモは **デプロイ前ビルド方式** を採用しています。Databricks Apps起動時にNode.js/npm buildを実行することはありません。本番のアプリプロセスは常にPythonのみです。デプロイ前に、ローカル環境またはCI環境でReactをProduction Buildし、生成された `frontend/dist` をデプロイ対象フォルダーへ含めます。

### 手動でビルドする場合

```bash
cd frontend
npm ci
npm run typecheck
npm run build
cd ..
```

### 一括スクリプトを使う場合

```bash
bash scripts/prepare_deploy.sh
```

`scripts/prepare_deploy.sh` は次を順番に実行し、いずれかが失敗した時点で処理を中断して非0の終了コードを返します。

1. `node` / `npm` / `python3`（または `python`）／ `pytest` が利用可能か確認する
2. `npm ci` でフロントエンド依存をインストールする
3. `npm run typecheck` でTypeScript型チェックを実行する
4. `npm run build` でProduction Buildを実行する
5. `frontend/dist/index.html` が生成されたことを確認する
6. `python -m pytest backend/tests -v` でPythonの主要テストを実行する
7. デプロイ対象に含めるべきファイル構成を一覧表示する

### ビルド確認

ビルド完了後、少なくとも以下が存在することを確認してください。

```text
frontend/dist/index.html
```

`frontend/dist/assets/` 配下にJS・CSSが生成されていることも確認してください。

## 9. Databricks Appsへの配置方法

`frontend/dist` は通常の開発コミットでは引き続きGit管理外（`.gitignore`）とします。ただし、**Databricks Appsへ配置する際は、ビルド済みの `frontend/dist` を必ず含めてください。**

### 推奨方式

1. `bash scripts/prepare_deploy.sh` を実行する
2. `frontend/dist/index.html` が生成されたことを確認する
3. `.gitignore` の有無にかかわらず、ローカルのビルド済みリポジトリフォルダー（`frontend/dist` を含む）をDatabricksワークスペースへ同期またはアップロードする
4. そのフォルダーをDatabricks Appsのソースとして指定する

### 避けるべき方式

GitリポジトリのURLから直接デプロイする方式は、`frontend/dist` がGit管理外であるため成果物が欠落し、UIが表示されないApp（APIのみ起動 or `APP_ENV=production` 設定時は起動失敗）になる可能性があります。Gitベースの自動デプロイを将来採用する場合は、**CIでビルド成果物を生成してからデプロイ対象へ配置する仕組み**（例：CIジョブが `scripts/prepare_deploy.sh` を実行し、`frontend/dist` を含んだ状態でワークスペースへ同期する）が必要です。この仕組みはPhase 1時点では未実装です。

### 再デプロイ

フロントエンドのコードを変更した場合は、**必ず `scripts/prepare_deploy.sh`（または手動ビルド）を再実行してから**、ビルド済みフォルダーを同期・再デプロイしてください。古い `frontend/dist` のまま再デプロイすると、変更が反映されません。

## 10. 起動モード（development / production）

`backend/config.py` の `resolve_app_env()` が `APP_ENV` 環境変数を読み、`production`（大文字小文字を区別しない）の場合のみproductionモードとして扱い、それ以外（未設定を含む）はdevelopmentモードとして扱います。

| モード | `frontend/dist/index.html` が無い場合の挙動 |
| --- | --- |
| development（既定） | APIのみで起動する（Viteの開発サーバーと併用する想定） |
| production（`APP_ENV=production`） | 起動を失敗させる（終了コード1、明確なエラーログを出力） |

productionモードで `frontend/dist/index.html` が無い場合、以下のエラーで起動が失敗します。

```text
frontend/dist/index.html が見つかりません。
scripts/prepare_deploy.sh を実行してから再デプロイしてください。
```

これにより、UIが欠落したままAPIだけが起動し「正常にデプロイされたように見える」状態を防ぎます。`app.yaml` はDatabricks Apps環境向けに `APP_ENV=production` を明示しています（詳細は本ファイル4節のディレクトリ構成、および `app.yaml` 本体を参照）。

既存のAPIパス・ポート解決優先順位（`DATABRICKS_APP_PORT` → `UVICORN_PORT` → `PORT` → `8000`）は変更していません。

## 11. ポート・ホスト解決

Pythonサーバーは次の優先順位で起動設定を解決します（`backend/config.py`）。

```text
Host: UVICORN_HOST → 0.0.0.0
Port: DATABRICKS_APP_PORT → UVICORN_PORT → PORT → 8000
```

- Databricks Appsでは、プラットフォームが提供する `DATABRICKS_APP_PORT` を優先して使用します。
- ローカル開発では `PORT` を設定でき、未設定の場合は8000を使用します。
- `app.yaml` 側では固定ポートを指定しません（起動コマンドと `APP_ENV` のみ定義）。
- 優先順位はホスト・ポートとも `backend/tests/test_config.py` で単体テスト済みです。

## 12. データモードの解決

`backend/config.py` の `resolve_data_mode()` が、以下3つのDatabricks SQL接続用環境変数がすべて設定されている場合のみ `databricks` モードを返し、それ以外は `demo` モードにフォールバックします。

- `DATABRICKS_SERVER_HOSTNAME`
- `DATABRICKS_HTTP_PATH`
- `DATABRICKS_TOKEN`

Phase 1では実際のDatabricks SQL接続は行わず、モード判定のみを実装しています。実データ接続はPhase 2以降で追加します。

## 13. Databricks Appsへのデプロイ手順

正確な操作はワークスペースUIと利用可能な機能に合わせて確認してください。完成条件は、ローカル起動ではなくDatabricks Apps上で表示できることです。

基本手順：

1. `bash scripts/prepare_deploy.sh` を実行し、`frontend/dist` を生成する（本README 8節）。
2. ビルド済みの `frontend/dist` を含むフォルダーを、Databricksワークスペースのフォルダーまたは同期先へ配置する（本README 9節。GitリポジトリのURLから直接デプロイする方式は `frontend/dist` が欠落するため避ける）。
3. Databricks Appsでカスタムアプリを作成する。
4. アプリのソースとして、ビルド済みフォルダーを選ぶ。
5. Databricks SQLに接続する場合は、必要なDatabricksリソース（SQLウェアハウス等）をアプリへ追加し、`DATABRICKS_SERVER_HOSTNAME` / `DATABRICKS_HTTP_PATH` / `DATABRICKS_TOKEN` に相当する接続情報を設定する。未設定の場合はdemoモードで起動する。
6. `app.yaml` の `APP_ENV=production` 設定により、Python起動処理がproductionモードで動作することを確認する（`frontend/dist/index.html` が無い場合はここで起動失敗する）。
7. Python起動処理が `DATABRICKS_APP_PORT` → `UVICORN_PORT` → `PORT` → `8000` の順でポートを解決し、ホストは `UVICORN_HOST` または `0.0.0.0` を使用することを確認する（`app.yaml` の起動コマンドは `python -m backend.main`）。
8. デプロイする。
9. アプリログと `/api/health` を確認する（200が返ること）。
10. `/api/metadata` で `data_mode` が想定通り（`demo` または `databricks`）であることを確認する。
11. **`/api/health` だけでなく、ブラウザでアプリを開いてUI（日本語ヘッダーと3カラムの空状態レイアウト）が実際に表示されることを確認する。**

## 14. API一覧

| メソッド・パス | 内容 | 備考 |
| --- | --- | --- |
| `GET /api/health` | 疎通確認 | `{"status": "ok"}` を返す |
| `GET /api/metadata` | アプリ全体のメタ情報 | `data_mode`, `model_mode`, `customer_count`, `updated_at` を含む |
| `GET /api/customers` | 本日の優先顧客一覧 | 顧客360と予測をcustomer_idで結合し、休眠確率の降順で返す |
| `GET /api/customers/{customer_id}` | 顧客360＋休眠予測の詳細 | 該当顧客が無ければ404（Japanese `detail` メッセージ） |
| `GET /api/customers/{customer_id}/recommendation` | 次アクション候補 | 要約・候補（最大3件）・理由・注意事項・参照元・生成方式を返す |
| `POST /api/customers/{customer_id}/decision` | 判断（承認／修正／見送り）の保存 | `decision_id`, `decided_at` を付与して返す |
| `GET /api/feedback-summary` | フィードバック概要 | 承認/修正/見送り件数、生成方式別件数、直近の判断一覧 |

`/api/customers` と `/api/customers/{customer_id}` は共通のレスポンス envelope（`data_mode`, `model_mode`, `updated_at`）を持つ。合成データ・予測結果が未生成の場合は503を返し、`scripts/generate_demo_data.py` → `scripts/prepare_customer360.py` → `scripts/train_model.py` の実行を促すメッセージを含む。

`recommendation` エンドポイントは `generation_mode` / `generation_mode_label`（本README 6節）を必ず含む。`decision` エンドポイントのリクエストボディは `decision`（`approved` / `modified` / `skipped`）、`selected_action`、`modified_text`、`comment`、`generation_mode`、`model_version` を受け付ける（いずれも `selected_action` 以降は任意）。

## 15. アプリの使い方（Phase 1〜4時点）

Phase 1〜4を通じて、Layer 1〜4の一連の業務フロー（Step①〜⑥）が一画面で完結します。画面各所の見出しには①〜⑥の番号を付け、デモを進める順序がひと目でわかるようにしています。

- ヘッダー：アプリ名、データモード（`合成データ（demo）` / `Databricks接続`）、モデルモード（`事前計算済み予測` / `実学習モデル`）、最終更新時刻。この4項目は常時ヘッダーで確認できる
- 左「① 本日の優先顧客」：休眠確率の降順に並んだ顧客リスト。リスク帯は色・アイコン・文字ラベルの3つで示し、色だけに依存しない。クリックで選択する
- 中央上「② 顧客360」：選択顧客のEC・QR決済/カード利用推移グラフ、利用サービス数（前期との比較）、最終利用日、問い合わせ件数、データソース一覧
- 中央下「③ 休眠リスク」：リスク帯、休眠確率、主要理由（最大3件、グラフの数値と一致）、モデルバージョン・推論日時
- 右「④ 次のアクション」：顧客状況の要約、アクション候補（最大3件、理由付き）、注意事項、参照元（社内ナレッジ文書）、生成方式（`LLM生成` / `事前生成済みLLM回答` / `デモ用ルールベース生成`）
- 右「⑤ 承認・修正・見送り」：④と同じパネル内で、アクションを選択し承認・修正・見送りを選び、コメントを添えて保存する。保存後は完了表示に切り替わる
- 下部「⑥ フィードバック概要」：承認・修正・見送りの件数、直近の判断一覧（生成方式込み）、自動再学習が未実装であることの明記
- 最下部「デモ構成／本番化時に追加する事項」（折りたたみ）：デモで実装済みの範囲と、本番化時に追加する範囲を分けて表示する。普段は閉じており、技術的な背景を説明したいときだけ開く

いずれかのAPI呼び出しが失敗した場合も、失敗した領域だけが日本語のエラーメッセージに切り替わり、他の領域は操作を継続できる（画面全体はクラッシュしない）。

## 16. 実装上の仮定

- 仮定：フロントエンドのビルド成果物（`frontend/dist`）は通常の開発コミットではGit管理対象外とし、デプロイ前に `scripts/prepare_deploy.sh`（または手動の `npm run build`）を実行して生成し、デプロイ時のみビルド済みフォルダーとして同期する。
- 理由：ビルド成果物を常にリポジトリへコミットすると、ソースとの差分管理が煩雑になり、依存関係の更新時に不整合が生じやすいため。一方でGit URLから直接デプロイするとビルド成果物が欠落するため、デプロイ時は「ビルド済みフォルダーを配置」という別の同期方式を用いる。
- 本番で確認する事項：Databricksワークスペースへの同期方法（Databricks CLIのsync、Reposのファイルアップロード等）が、`frontend/dist` を含むフォルダー全体を正しく反映できるか確認する。CI/CDパイプラインを導入する場合は、CIが `scripts/prepare_deploy.sh` を実行してから同期する運用にする。

- 仮定：`app.yaml` の `env` セクションで `APP_ENV=production` をキーバリュー形式（`name`/`value`）で指定できると仮定している。
- 理由：Databricks Appsのapp.yaml仕様のうち、非シークレットな環境変数を設定する一般的な記法として妥当と判断したため。
- 本番で確認する事項：実際のDatabricksワークスペースにデプロイする際、`app.yaml` の `env` セクションの記法がワークスペースのDatabricks Appsバージョンで有効か確認する。無効な場合は、Databricks Appsのアプリ設定UIから環境変数 `APP_ENV=production` を追加する。

- 仮定：Phase 1では `requirements.txt` にDatabricks SQL接続用ライブラリ（`databricks-sql-connector` 等）を含めていない。
- 理由：Phase 1の受け入れ条件は起動・ヘルスチェック・メタデータ・モード判定のみであり、実データ接続はPhase 2以降のスコープのため。
- 本番で確認する事項：Phase 2でDatabricks SQLへの実接続を実装する際に、必要なライブラリと接続処理を追加する。

- 仮定：ルートに `package.json` を置かず、`frontend/package.json` のみでNode依存関係を管理する。
- 理由：Node.jsはフロントエンドのビルド専用であり、ルートにNodeパッケージを持つ必然性がないため（本番プロセスはPythonのみ）。
- 本番で確認する事項：Databricksへのデプロイ手順で、ビルドを `frontend/` 配下で実行する運用が周知されているか確認する。

- 仮定：合成データ生成の基準日（`AS_OF_DATE`）を `2026-07-16` に固定し、`datetime.now()` は使わない。
- 理由：実行日に依存せず完全な再現性を保証するため。「未来日付にならない」というデータ品質要件も、この固定日付を基準に判定している。
- 本番で確認する事項：デモ実施日と基準日が大きくかけ離れる場合、「最終利用日からの経過日数」の見え方に違和感が出る可能性があるため、デモ実施前に基準日を実行時点へ更新するかを検討する。

- 仮定：休眠リスクの正解ラベルが存在しない合成データのため、EC/QR・カードの累積低下率、利用サービス数減少、直近利用からの経過日数、施策反応、問い合わせ有無を重み付け合成した決定論的スコアをもとに、教師ラベルをベルヌーイ試行でサンプリングして生成した。
- 理由：DEMO_SPEC.mdは「経済的な休眠の兆候」を測る単純で説明可能なモデルを求めており、実データの解約フラグが存在しない以上、業務的に妥当なルールから疑似ラベルを作る以外に方法がないため。
- 本番で確認する事項：実際の解約・休眠実績データが利用可能になった時点で、このルールベースのラベルを実績ラベルに置き換え、モデルを再学習する。

- 仮定：リスク帯のしきい値（高0.66以上、低0.34未満）は固定値とし、パーセンタイルなど分布依存の動的しきい値は採用していない。
- 理由：DEMO_SPEC.mdの例示（高0.72〜0.84、中0.40〜0.64、低0.08〜0.30）に近い固定範囲の方が、担当者にとって毎回の分布の揺れに影響されず一貫した目安になるため。
- 本番で確認する事項：合成データの規模やモデル更新により、特定の帯に極端に偏る場合はしきい値の再調整、または分布ベースの動的しきい値への切り替えを検討する。

- 仮定：休眠リスクのスコアリングは、EC・QR決済・カードの利用額と利用サービス数、直近利用からの経過日数、施策反応、問い合わせ有無のみを対象とし、銀行取引はスコアの入力に含めない（顧客360の表示・最終利用日の全体判定には含める）。
- 理由：DEMO_SPEC.mdの必須データソースがEC・QR決済・カードであり、銀行は任意データソースであるため、モデルの説明可能性を優先し必須ソースに絞った。
- 本番で確認する事項：銀行データの重要性が高いと判断された場合、スコアリング式へ銀行の特徴量を追加し、再学習・再検証する。

- 仮定：実LLMエンドポイントのリクエスト・レスポンス形式は、OpenAI互換のchat completions形式（`messages` 配列、レスポンスは `choices[0].message.content` にJSON文字列）であると仮定している。
- 理由：利用するLLMエンドポイントの実装がこの時点で確定していないため、多くのLLMサービス・Databricks Model Servingの一部構成でも採用される一般的な形式を仮の契約とした。
- 本番で確認する事項：実際に接続するLLMエンドポイント（Databricks Model Serving等）のリクエスト・レスポンス形式を確認し、`backend/services/llm_client.py` の `_call_endpoint` を実際の形式に合わせて調整する。

- 仮定：事前生成済みLLM回答（`artifacts/pre_generated_recommendations.json`）は60顧客中6顧客（高・中・低リスクから2件ずつ）のみを用意し、対象外の顧客はルールベース生成にフォールバックする。
- 理由：全60顧客分の事前生成済み回答を用意することは本フェーズの検証目的（3方式の切り替えが正しく動くことの実証）に対して過剰であり、ルールベース生成が全顧客をカバーする最終フォールバックとして機能するため、6件で切り替えロジックの実証は十分と判断した。
- 本番で確認する事項：デモで見せたい顧客が6件に含まれない場合、`scripts/generate_pregenerated_recommendations.py` の `PRE_GENERATED_CONTENT` へ対象顧客を追加する。

- 仮定：判断保存は既定でリポジトリ直下の `runtime/decisions.json`（Git管理外）へのファイル書き込みとする。Databricksデータモード（`DATABRICKS_SERVER_HOSTNAME` 等が設定済み）の場合でも、Databricks側の保存先接続は未実装のため、警告ログを出したうえで同じファイルストレージへフォールバックする。
- 理由：DEMO_SPEC.mdの要件は「永続ストレージが未設定でも動くこと」であり、Databricks Free Edition環境での確実な動作を優先した。Databricks側の実装（Delta テーブルへの書き込み等）は接続方式の検証が必要なため、本フェーズのスコープ外とした。
- 本番で確認する事項：Databricks側の判断保存先（Delta テーブル等）を用意し、`backend/services/decision_store.py` の `_get_databricks_store` を実装に置き換える。

- 仮定：ルールベース生成が提案するアクションは、DEMO_SPEC.mdが例示する5種類（EC再利用の案内／QR決済の利用メリット案内／カード利用特典の案内／複数サービスをまたぐ軽量なポイント施策／施策を行わず経過観察）に固定し、それ以外の自由記述アクションは生成しない。
- 理由：推奨アクションが業務方針から逸脱しないことを構造的に保証するため（自由記述だと過度なインセンティブ等が紛れ込むリスクがある）。
- 本番で確認する事項：実際の施策カタログが追加・変更された場合、`backend/services/rule_based_generator.py` のアクション定数とナレッジ文書（`data/knowledge/knowledge_base.json`）を合わせて更新する。

## 17. 失敗時の対処

`frontend/dist/index.html` が見つからずproductionモードで起動が失敗した場合：

1. ログに出力された `frontend/dist/index.html が見つかりません。scripts/prepare_deploy.sh を実行してから再デプロイしてください。` を確認する。
2. ローカルで `bash scripts/prepare_deploy.sh` を実行し、型チェック・ビルド・テストがすべて成功することを確認する。
3. 生成された `frontend/dist` を含むフォルダーを、Databricksワークスペースの配置先へ再同期する。
4. Databricks Appsを再デプロイし、アプリログと `/api/health`・画面表示の両方を再確認する。

## 18. デモ前チェック・データ品質テスト結果（Phase 1〜4時点で確認済みの項目）

### 起動・デプロイ関連（Phase 1）

- [x] `python -m pytest backend/tests` が全件成功する（development/productionモードの起動挙動を含む）
- [x] `npm run typecheck` がエラーなく完了する
- [x] `npm run build` が成功し `frontend/dist/index.html` を含む成果物が生成される
- [x] `bash scripts/prepare_deploy.sh` が最後まで成功し、終了コード0を返す
- [x] `bash scripts/prepare_deploy.sh` は型チェック失敗時に後続処理を実行せず、終了コード1で停止する
- [x] developmentモード（`APP_ENV`未設定）では `frontend/dist` が無くても `python -m backend.main` が起動し、`/api/health` が200を返す
- [x] productionモード（`APP_ENV=production`）で `frontend/dist/index.html` が無い場合、`python -m backend.main` が明確なエラーで起動失敗する（終了コード1）
- [x] productionモードで `frontend/dist` が存在する場合、`/api/health` ・`/api/metadata` ・`/`（index.html）がいずれも200を返す
- [x] `/` への複数回のGETで、同じindex.htmlが返る（ページリロードを想定した確認）
- [ ] Databricks Apps上での実デプロイ確認（この修正では未実施、ワークスペースアクセスが必要）

### データ品質（Phase 2、`backend/tests/test_data_quality.py` で自動検証済み）

- [x] 負の金額がない
- [x] 全期間ゼロの主要顧客がいない
- [x] 高リスク顧客は利用低下または利用サービス数減少のいずれかを示す
- [x] 低リスク顧客の休眠確率が全員同一ではない
- [x] 休眠確率が0または1に張り付かない（実測範囲 0.03〜0.926）
- [x] リスク帯の分布に高・中・低がすべて含まれる（実測：高16／中9／低35）
- [x] 予測理由のテキストが顧客360の実データ（前期比の数値）と一致する
- [x] 日付が未来にならない（基準日2026-07-16を超える取引なし）
- [x] 最終利用日と利用履歴が矛盾しない（生データから直接導出しているため構造的に保証）
- [x] 同一customer_idが重複しない
- [x] 金額が日本円として常識的な範囲（0〜500,000円）に収まる
- [x] 合成データ生成を再実行しても同じ結果になる（タイムスタンプ以外が完全一致することを確認済み）
- [x] `GET /api/customers`, `GET /api/customers/{customer_id}` の疎通・404応答（`backend/tests/test_customers_api.py`）
- [x] Databricksモード設定時に未実装のためdemoへフォールバックすること（`backend/tests/test_data_source.py`）

### 推奨アクション・判断・フィードバック（Phase 3）

- [x] `GET /api/customers/{customer_id}/recommendation` が顧客360と予測結果を参照した結果を返す（`backend/tests/test_recommendation_api.py`）
- [x] ナレッジ文書の参照元（`references`）が返り、実在する`doc_id`のみで構成される（ハルシネーション拒否を含む、`backend/tests/test_llm_client.py`）
- [x] LLM設定済み・成功時は実LLMが主経路になる（モックで検証、`test_uses_llm_when_configured_and_successful`）
- [x] LLM失敗時は事前生成済み回答へ移行する（`test_falls_back_to_pre_generated_when_llm_fails`）
- [x] 事前生成済み回答が無い場合はルールベースへ移行する（`test_falls_back_to_rule_based_when_llm_fails_and_no_pre_generated_fixture`）
- [x] 不正なLLM出力（空文字・4件超のactions・許可されない参照元）は安全にフォールバックする（`test_generate_rejects_*`）
- [x] LLM未設定でも動く（既定状態で全テストがLLM未設定のまま成功）
- [x] 生成モードがAPI（`generation_mode`）とUI（バッジ表示）で一致する
- [x] 高リスク顧客でも「施策を行わず経過観察」が候補から排除されない（`test_recommendation_never_forces_action_for_high_risk`）
- [x] 判断（承認／修正／見送り）を保存できる。404（存在しない顧客）・422（不正な`decision`値）を確認済み
- [x] 保存後にフィードバック概要（件数・生成方式別内訳・直近一覧）が変化する（`test_feedback_summary_reflects_saved_decisions`）
- [x] 自動配信・自動再学習を実装しておらず、フィードバック概要に「本番化時に追加」と明記している
- [x] ブラウザでStep 1〜6（顧客選択→顧客360→休眠リスク→次アクション→承認/修正/見送り→フィードバック概要反映）を実行できることをPlaywrightで確認済み

### UI完成・デモ整合性（Phase 4）

- [x] 推奨アクションが過去の施策反応と矛盾しない：同一施策種別に過去「反応なし」があった場合、優先度を下げたうえで注意事項に明記する（`test_recommendation_acknowledges_past_no_response_for_same_channel`、全60顧客で確認）
- [x] 代表的な高・中・低リスク顧客（C059, C015, C060等）についてグラフ・予測理由・推奨アクション・過去施策反応の整合性を目視確認
- [x] 予測確率は0.03〜0.926の範囲で、0または1に張り付いていない
- [x] API通信が失敗した場合、失敗した領域のみ日本語のエラーメッセージへ切り替わり、他の領域は操作可能なまま維持される（Playwrightでネットワーク遮断を模擬して確認）
- [x] 各パネルを`ErrorBoundary`で分離し、一領域の描画エラーが画面全体をクラッシュさせない
- [x] ヘッダーにデータモード・モデルモード・最終更新が常時表示される
- [x] リスク表示は色・アイコン・文字ラベルの組み合わせで、色だけに依存しない
- [x] 金額（`toLocaleString("ja-JP")`+円）、日付（`toLocaleString("ja-JP")`）、パーセント（四捨五入＋%）の表記が日本語として自然である
- [x] 実績ではない数値（モデル評価値等）を成果として画面に表示していない
- [x] `npm run typecheck` / `npm run build` / `python -m pytest backend/tests`（65件）が全件成功する
- [x] Step①〜⑥の一連の操作をPlaywrightで最初から最後まで実行し、スクリーンショットで確認済み

## 19. 伝えること・伝えないこと

### 伝えること
- 部門別データを一人の顧客像へ統合する設計であること
- 予測は優先順位を付けるために使うこと
- GenAIは予測を置き換えず、データと社内方針を基に判断材料を整理すること
- 最終判断は担当者が行うこと
- 結果を次の予測と施策改善へ戻すこと

### 伝えないこと
- このデモだけで本番セキュリティが完成していること
- AIが最適施策を保証すること
- Databricksでしか実現できないこと
- デモの改善率が実績であること
- モック連携が本番APIであること
