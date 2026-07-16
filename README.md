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

## 2. 現在の実装状況（Phase 1〜6）

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
- 技術詳細・本番化境界を折りたたみ式の「デモ構成／本番化時に追加する事項」へ隔離し、通常時は非表示にする（※Databricks Appsへの実デプロイ後、利用者の依頼によりこのパネルとフッターの一文は削除。本README 17節参照）
- APIエラー・ネットワーク障害時も日本語メッセージを表示し、各パネルを`ErrorBoundary`で分離することで、一部の表示エラーが画面全体をクラッシュさせないようにする
- ルールベース生成が、過去に同じ施策種別で「反応なし」だった場合にその旨を注意事項へ明記し、優先度を下げるよう改善（推奨とフィードバック履歴の矛盾を防止）
- 高・中・低リスクの代表顧客についてデータ・予測・推奨の整合性を確認（本README 26節参照）

### Phase 5（テスト・Databricks Apps対応・Free Edition向け堅牢化）
- SPAフォールバック（`/api/*`以外の未知パスでも`index.html`を返す）を追加し、静的ファイル配信とAPIルートが競合しないことをテストで確認
- 判断保存先が書き込み不可（読み取り専用ファイルシステム等）の場合、インメモリストレージへ自動フォールバックし、`persisted`フィールドで永続化状況をAPI・UIへ明示
- APIリクエストの文字数上限（コメント等2000字、選択アクション200字）を追加し、無制限入力を防止
- 依存関係・ログ出力・CORS設定を点検（未使用依存なし、秘密情報のログ出力なし、CORSは同一オリジンのため意図的に未設定）
- フロントエンドの単体テスト（Vitest + Testing Library）を追加し、`scripts/prepare_deploy.sh`に組み込み
- Databricks Free Edition向けの確認事項をREADMEへ集約（本README 14節）

### Phase 6（Databricks Appsへのデプロイ、最終受け入れ、デモ運用資料）
- コード・依存関係の最終監査（未使用コード・未使用依存の有無を確認。削除対象なし）
- `CLAUDE.md`・`DEMO_SPEC.md`の受け入れ条件を項目ごとに確認（本README 27節）
- 実際のDatabricks Apps環境への接続を試行し、結果を正直に記録（本README 22節。この実行環境からは接続不可のため、実デプロイは未実施）
- Free Edition環境でのアプリ停止を想定した再起動・再デプロイ手順を整理（本README 23節）
- デモ失敗時のバックアップ手順と代表顧客の固定シナリオを整理（本README 24節）
- デモ実演用の短縮操作手順を追加（本README 25節）
- 本番化時に追加する設計・既知の制約を一覧化（本README 26節・27節）

### デプロイ後の追加修正
- Databricks Repos経由のデプロイでは`frontend/dist`がGit管理外だと反映されないことが実機で判明し、ビルド成果物をGit管理下に含める方式へ変更（本README 9節・18節）
- 利用者の依頼により、画面下部の「デモ構成／本番化時に追加する事項」パネル、フッターの一文、「⑥ フィードバック概要」内の本番化注記（APIの`note`フィールドを含む）を削除。この時点でUI・APIのいずれにも本番化境界の明示は残っていない（本README 17節「本番化境界パネルの削除について」参照）
- Step 6「フィードバック概要」に、施策後の反応・利用再開のデモ用サンプル表示を追加し、改善ループ（判断→施策→反応→利用再開→次の分析・モデル・施策改善）を画面上で完結させた（`artifacts/sample_campaign_outcomes.json`、`backend/services/sample_outcomes.py`、`GET /api/feedback-summary`の`sample_outcomes`フィールド、本README 6節）
- Step 6に、施策後の反応・利用状況から次の推奨アクション（固定8カテゴリのルールベース判定）と、全顧客を集計した「今回の改善ポイント」を追加し、結果確認だけで終わらない画面にした（`backend/services/feedback_action_service.py`、`recommended_next_action`/`improvement_summary`フィールド、本README 6節「次の改善アクション」）

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
│   ├── pre_generated_recommendations.json
│   └── sample_campaign_outcomes.json    # 施策後の反応・利用再開のデモ用固定サンプル（本README 6節）
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
│   │   ├── feedback_service.py          # フィードバック概要の集計（判断＋サンプル反応の結合）
│   │   └── sample_outcomes.py           # 施策後の反応・利用再開の固定サンプル読み込み
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
│       ├── test_decision_and_feedback.py   # 判断保存・フィードバック概要のテスト
│       └── test_decision_store_fallback.py # 書き込み不可時のインメモリフォールバックのテスト
├── frontend/
│   ├── package.json
│   ├── package-lock.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── vitest.config.ts                # 単体テスト設定（jsdom環境）
│   ├── index.html
│   ├── dist/                           # npm run build で生成。Git管理対象（Databricks Repos経由のデプロイに必要。本README 9節）
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── App.css
│       ├── types.ts
│       ├── api/client.ts
│       ├── test/setup.ts               # Testing Libraryのクリーンアップ・jest-dom設定
│       ├── components/
│       │   ├── CustomerListPanel.tsx
│       │   ├── CustomerListPanel.test.tsx
│       │   ├── Customer360Panel.tsx
│       │   ├── RiskPanel.tsx
│       │   ├── UsageTrendChart.tsx
│       │   ├── RiskBadge.tsx
│       │   ├── RiskBadge.test.tsx
│       │   ├── RecommendationPanel.tsx  # 次のアクション（要約・候補・承認/修正/見送り）
│       │   ├── RecommendationPanel.test.tsx
│       │   ├── ErrorBoundary.tsx        # パネル単位の描画エラー分離
│       │   ├── FeedbackSummaryPanel.tsx # フィードバック概要（判断集計＋施策後の反応サンプル）
│       │   └── FeedbackSummaryPanel.test.tsx
│       └── styles/
│           ├── tokens.css
│           └── global.css
├── generate_ecommerce_sample_data.py   # Databricksノートブック用（Phase 1以前から存在）
└── save_bronze_delta_tables.py         # Databricksノートブック用（Phase 1以前から存在）
```

### 最終ファイル構成の説明（Phase 6）

Databricks Appsへの配置観点で、上記構成を役割ごとに分類する。

**Databricks Appsへのデプロイに必須（同期対象）**
- `app.yaml`：起動コマンドと `APP_ENV=production` の宣言
- `requirements.txt`：backendの実行時依存（fastapi, uvicorn, httpx, pytest）
- `backend/`：FastAPIアプリ本体
- `data/`・`artifacts/`：合成データと事前計算済み結果（バックアップ・フォールバック用、本README 23節）
- `frontend/dist/`：ビルド済みReact成果物（`bash scripts/prepare_deploy.sh` で生成。Databricks Repos経由のデプロイに対応するためGit管理対象としている。コードを変更するたびに再ビルド・再コミットが必要。本README 9節・18節）

**開発・データ生成専用（Databricks Apps起動時には不要）**
- `scripts/`：合成データ生成・顧客360統合・モデル学習・事前生成済み回答作成・デプロイ前ビルドスクリプト一式。`scripts/requirements-scripts.txt`（scikit-learn, numpy）はこれらのスクリプト実行時のみ必要で、backend実行時には読み込まれない。
- `frontend/src/`・`frontend/package.json` 等：Reactのソースコードとビルド設定。ビルド後は `frontend/dist/` のみが実行時に使われる。
- `CLAUDE.md`・`DEMO_SPEC.md`・`README.md`：仕様・開発方針・利用方法のドキュメント。アプリの動作には関与しない。

**アプリ実行時に生成される状態（Git管理外）**
- `runtime/decisions.json`：判断保存の既定の書き込み先。書き込み不可の場合は自動的にインメモリへフォールバックする（本README 13節）。

**Phase 1以前から存在するレガシーファイル（本アプリからは未参照）**
- `generate_ecommerce_sample_data.py`・`save_bronze_delta_tables.py`：Databricksノートブック上でBronzeレイヤーのDelta テーブルを作成するための独立したスクリプト。DEMO_SPEC.mdの必須要件（本アプリの合成データパイプラインは `scripts/generate_demo_data.py` 以降を使用）には含まれておらず、本アプリのbackend/frontendからも読み込まれない。Phase 6の監査でも本アプリの実行フローと無関係であることを確認し、既存ファイルを削除する積極的な理由もないため、そのまま保持している（未使用コードとして削除する場合は、この2ファイルが必要ないことを利用者側でも確認のうえ判断されたい）。

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
- DEMO_SPEC.mdの「データ品質の必須検証」は、生成スクリプト内の即時チェック（違反時は非0終了）と `backend/tests/test_data_quality.py` の両方でカバーしている（本README 26節「データ品質」参照）。

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
- リクエストはOpenAI互換のchat completions形式（`messages` に system/user、レスポンスは `choices[0].message.content` がJSON文字列）を想定している。Databricks Model Serving等、実際に利用するエンドポイントの形式に合わせて `_call_endpoint` を調整する必要がある（本README 18節「実装上の仮定」参照）。
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

### フィードバックループ（Step 6：施策後の反応・利用再開サンプル）

DEMO_SPEC.mdのStep 6「改善ループを確認する」を画面上で完結させるため、「⑥ フィードバック概要」に、施策後の反応・利用再開の**デモ用固定サンプル**を追加している。

- `artifacts/sample_campaign_outcomes.json`：6名の代表顧客（`C059`, `C017`, `C015`, `C045`, `C010`, `C031`。本README 22節の代表顧客と同一）について、`campaign_status`（実施済み／施策未実施）・`customer_response`（メール開封／案内ページ閲覧／クーポン利用／問い合わせ／反応なし／施策未実施）・`usage_recovery_status`（30日以内に利用再開／一部サービスで利用再開／利用再開なし／観測期間中／施策未実施）・`observed_at`・`is_sample: true` を固定値で保持する。固定シードの合成データとは異なりランダム生成ではなく、手作業で作成した固定JSONであるため、実行するたびに同じ内容になる。
- `backend/services/sample_outcomes.py`がこのJSONを読み込み、`backend/services/feedback_service.py`の`build_feedback_summary()`が、各サンプル対象顧客について**実際に保存された最新の判断**（`decision`・`selected_action`・`comment`・`decided_at`）があれば結合し、無ければ`decision: null`（未対応）として返す。反応・利用再開の値自体は判断の有無に関わらず常に固定サンプルのままである。
- `GET /api/feedback-summary`のレスポンスに`sample_outcomes`フィールドとして追加される（既存フィールドは変更しておらず、後方互換）。
- UIでは「施策後の反応と利用状況」という見出しの下にカード一覧を表示する（`frontend/src/components/FeedbackSummaryPanel.tsx`）。
- 実際のメール・クーポン配信、CRM/キャンペーンシステムとの接続、実顧客の施策結果取り込みは行っていない（本README 24節）。

### サンプルである旨の画面表示の変遷

追加当初は、見出し「施策後の反応と利用状況（デモ用サンプル）」・サンプルである旨の注記・判断の活用目的を説明する文の3箇所でサンプルであることを明示していたが、その後利用者の依頼によりいずれも一度削除した（画面上にはサンプルである旨の明示が一切ない状態になった）。その後、次の推奨判断機能を追加するにあたり、利用者から改めてサンプルである旨の注記を追加する依頼があり、`frontend/src/components/FeedbackSummaryPanel.tsx`に「施策後の反応、利用状況、次の推奨判断は、改善ループを説明するためのデモ用サンプルです。」という注記を再度表示するようにした。現時点ではこの注記が画面上に表示されている。

バックエンドの`sample_outcomes`レスポンスには引き続き`is_sample: true`が含まれており、API上でも常にサンプルであることを判別できる。

### 次の改善アクション（Step 6：推奨アクションと全体改善サマリー）

Step 6を結果確認だけで終わらせず、「続ける施策・見直す施策・次に検証する内容」を判断できる画面にするため、施策後の反応・利用状況から次の推奨アクションをデモ用の説明可能なルールベースで導出し、あわせて全体の改善サマリーを表示する。

- `backend/services/feedback_action_service.py`の`determine_next_action()`が、担当者判断・施策実施状況・顧客の反応・利用再開状況を入力に、固定8カテゴリ（類似顧客へ展開／オファー内容を変更／接触チャネルを変更／接触タイミングを変更／対象顧客の条件を見直す／継続観測／施策効果を再検証／今回の施策を停止）から1つを決定論的に選び、`type`・`label`・`reason`・`next_review_timing`を返す。外部LLMや機械学習モデルは使用しない。判定の優先順位は次の通り。
  1. 担当者判断が「見送り」の場合、反応・利用再開の内容に関わらず「対象顧客の条件を見直す」
  2. 利用状況が「観測期間中」の場合、「継続観測」
  3. 施策自体が未実施の場合、「継続観測」
  4. それ以外は、施策後の反応（メール開封／案内ページ閲覧／クーポン利用／問い合わせ＝反応あり、反応なし＝反応なし）と利用再開の有無を組み合わせて、類似顧客へ展開／オファー内容を変更／接触チャネルを変更／施策効果を再検証のいずれかを決定する
  - 担当者判断が「修正して承認」の場合は理由文に修正内容を、「承認」の場合は次回の施策評価へ活用する旨を追記する
- 同じ入力に対しては常に同じ結果を返す（乱数・外部呼び出しなし）。未知の値・欠損値が渡された場合も例外を送出せず、安全な既定値へフォールバックする。
- `backend/services/feedback_action_service.py`の`build_improvement_summary()`が、全顧客の推奨アクション種別を「継続・展開候補」「見直し候補」「次回検証する仮説」の3つに集計し、代表例をもとに1文ずつ生成する。対象が0件の場合は無理に文章を作らずNoneのまま返す。
- `GET /api/feedback-summary`のレスポンスへ、各`sample_outcomes`要素に`recommended_next_action`（`type`/`label`/`reason`/`next_review_timing`）を追加し、`improvement_summary`（`expand_candidates`/`review_candidates`/`next_hypothesis`、いずれもデータが無ければ`null`）フィールドを新設した。既存フィールドは変更していない（後方互換）。
- UIでは各サンプルカードに「次の推奨判断」（色だけでなく文字で表示する青系バッジ）・「理由」・「次回確認」を追加し、カード一覧の下に「今回の改善ポイント」ブロックを表示する。改善ポイントが無い場合は「現時点では十分な結果がありません。追加の施策結果を確認後、改善候補を表示します。」と表示する。
- Step 6の最後に「担当者の判断と施策結果を基に、続ける施策、見直す施策、次に検証する内容を決定します。」という文章を一度だけ表示する。
- 施策の自動配信、次の施策の自動実行、モデルの自動再学習、自動的な顧客セグメント変更、因果推論による施策効果測定、A/Bテストの自動作成、CRM/MAツールへの自動連携、実顧客データによる効果判定、LLMによる自由生成の改善提案は、いずれも実装していない（本README 24節）。

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

# 単体テスト（Vitest + Testing Library）
npm run test
```

developmentモードでは `frontend/dist` の有無にかかわらずPython APIが起動するため、`npm run dev` の開発サーバーと `python -m backend.main` を並行起動して開発できます。

## 8. デプロイ前ビルド（Production Build）

このデモは **デプロイ前ビルド方式** を採用しています。Databricks Apps起動時にNode.js/npm buildを実行することはありません。本番のアプリプロセスは常にPythonのみです。デプロイ前に、ローカル環境またはCI環境でReactをProduction Buildし、生成された `frontend/dist` をデプロイ対象フォルダーへ含めます。

### 手動でビルドする場合

```bash
cd frontend
npm ci
npm run typecheck
npm run test
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
4. `npm run test` でフロントエンドの単体テスト（Vitest）を実行する
5. `npm run build` でProduction Buildを実行する
6. `frontend/dist/index.html` が生成されたことを確認する
7. `python -m pytest backend/tests -v` でPythonの主要テストを実行する
8. デプロイ対象に含めるべきファイル構成を一覧表示する

### ビルド確認

ビルド完了後、少なくとも以下が存在することを確認してください。

```text
frontend/dist/index.html
```

`frontend/dist/assets/` 配下にJS・CSSが生成されていることも確認してください。

## 9. Databricks Appsへの配置方法

**Databricks Appsへ配置する際は、ビルド済みの `frontend/dist` を必ず含めてください。** 配置方法はワークスペースの同期方式によって2通りある。

### 方式A：手動同期・Databricks CLI（`frontend/dist` はGit管理外のまま）

1. `bash scripts/prepare_deploy.sh` を実行する
2. `frontend/dist/index.html` が生成されたことを確認する
3. ローカルのビルド済みリポジトリフォルダー（`frontend/dist` を含む）を、`databricks sync` 等でDatabricksワークスペースへ同期する
4. そのフォルダーをDatabricks Appsのソースとして指定する

### 方式B：GitHub連携のDatabricks Repos機能を使う場合（`frontend/dist` をGit管理下に含める）

**Databricks ReposはGit管理下のファイルしか同期しない。** `frontend/dist` を通常通り`.gitignore`対象のままにすると、Repos経由のデプロイでは成果物が欠落し、`FrontendBuildMissingError`で起動が失敗する（本リポジトリで実際に発生し確認済みの障害）。Repos経由でデプロイする場合は、次の手順を取る。

1. `.gitignore` から `frontend/dist/` の除外を外す（本リポジトリは既にこの設定にしてある）
2. `bash scripts/prepare_deploy.sh`（Windowsでbashが無い場合はGit Bash、または `cd frontend && npm ci && npm run typecheck && npm run test && npm run build`）を実行してビルドする
3. `git add frontend/dist` でビルド成果物をコミットし、pushする
4. Databricksワークスペースの該当Repoを最新コミットへ同期（Pull）する
5. Databricks Appsを再デプロイする

この方式は、ビルド成果物をリポジトリへコミットするという通常の開発慣行からは外れるが、Databricks Reposを使う場合に確実に動作させるための実務上の対応である（本README 18節「実装上の仮定」参照）。

### 再デプロイ

フロントエンドのコードを変更した場合は、**必ず `scripts/prepare_deploy.sh`（または手動ビルド）を再実行してから**、方式Aは同期、方式Bはコミット・push・Repoの同期を行ってください。古い `frontend/dist` のまま再デプロイすると、変更が反映されません。

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

## 13. セキュリティ・堅牢化（Phase 5）

Databricks Free Edition／Databricks Apps環境で確実に動かすため、以下を確認・実装した。

### SPAフォールバックとAPIルートの分離

- `backend/main.py` は `frontend/dist/index.html` が存在する場合、`/api/*` 以外の未知のパス（直リンクやブラウザの再読み込み）でも404にせず `index.html` を返すフォールバックを実装している（`spa_fallback_handler`）。現状は1画面構成でクライアントサイドルーティングを持たないが、Databricks Appsのプロキシ挙動や将来のルーティング追加に備えた保険である。
- `/api/*` の404は引き続きJSONの日本語 `detail` メッセージのまま返し、`index.html` へ差し替えない（`backend/tests/test_deploy_modes.py` の `test_unknown_api_path_stays_json_404_not_spa_index` で確認）。
- APIルーターは静的ファイルのマウントより前に登録しているため、`/api/health` 等が静的ファイル配信に奪われることはない（同ファイルの `test_unknown_non_api_path_falls_back_to_spa_index` 等で確認）。

### 判断保存の書き込み失敗への対応

- `backend/services/decision_store.py` は、判断保存先ディレクトリへの書き込み可否を毎回軽量に確認し（一時ファイルを作成・削除するprobe）、書き込めない場合は例外で失敗させず、プロセス内メモリのフォールバックストア（`InMemoryDecisionStore`）へ自動的に切り替える。
- レスポンスの `persisted` フィールド（`POST /api/customers/{id}/decision` のレスポンス、`GET /api/feedback-summary` の `storage_mode`/`persisted`）で、実際に永続化されたかどうかを利用者が画面上で確認できる。UIは `persisted: false` の場合に「一時保存です。アプリ再起動で失われる可能性があります」という警告を表示する。
- Databricks Apps環境でコンテナのファイルシステムが読み取り専用、または再起動でファイルが失われる場合でも、判断保存API自体は失敗せずに動作し続ける（`backend/tests/test_decision_store_fallback.py` で、権限に依存しない失敗パス（親コンポーネントがファイルであるパス）を使って検証済み）。

### API入力検証

- `POST /api/customers/{customer_id}/decision` はPydanticで `decision` を `approved`/`modified`/`skipped` のいずれかに限定し、`comment`・`modified_text` は2000字、`selected_action`は200字を上限とする（超過時は422）。無制限の入力によるリソース消費を避けるための最小限の制限であり、業務要件を追加するものではない。

### CORS

- フロントエンドとバックエンドは常に同一オリジン（PythonがReactビルドを配信し、開発時もViteが `/api` をプロキシする）で通信するため、`CORSMiddleware` は導入していない。クロスオリジンアクセスを許可する設定を追加する必要はなく、意図的に何も設定していない。

### ログ出力の点検

- LLM呼び出し失敗時は例外の型名（`type(exc).__name__`）のみを記録し、リクエストヘッダー・レスポンス本文・認証情報を一切ログへ出力しない（`backend/services/llm_client.py`）。
- Databricks/ファイルストレージのフォールバック時のログは、固定文言とローカルパス・匿名customer_id（例：`C001`）のみで、顧客の氏名・コメント本文・秘密情報は含まない。
- リポジトリ全体を点検し、環境変数やAPIキーを `print`/`logger` へ出力する箇所がないことを確認済み。

### 依存関係の点検

- `requirements.txt`（fastapi, uvicorn, httpx, pytest）、`scripts/requirements-scripts.txt`（scikit-learn, numpy）、`frontend/package.json` の全依存関係を確認し、いずれも実際にコード内で使用されていることを確認した（未使用の依存は無かったため削除対象はなし）。
- `app.yaml` の起動コマンドはPythonのみであり、Node.js/Expressがバックエンドとして起動することはない。

## 14. Databricks Free Edition向けの確認事項

- **サーバーレス・クォータ制限環境であること**：Databricks Free Editionはサーバーレスコンピュートで動作し、計算量やリソースに制限がある。本デモは合成データ60顧客・軽量なロジスティック回帰・事前計算済み予測を用いることで、この制約下でも動作するように設計している。
- **アプリが停止した場合の再起動方法**：Databricks Appsのアプリ管理画面からアプリを再起動する。`data/`・`artifacts/` はリポジトリにコミット済みのため、再起動時に合成データや事前計算済み予測を再生成する必要はない。判断履歴（`runtime/decisions.json`）はGit管理外のため、コンテナの永続ディスクが再起動をまたいで保持されない構成の場合は失われる可能性がある（本README 13節）。
- **外部サービスを必須にしていないこと**：実LLMエンドポイント・Databricks SQL・Unity Catalogのいずれも未設定で起動できる。デフォルトでは合成データ（`demo`モード）と、事前生成済み回答／ルールベース生成のみで、Step①〜⑥のデモフロー全体が完走する。
- **モデルサービングやVector Searchなしでもデモ可能であること**：休眠予測は `scripts/train_model.py` で事前学習・事前計算した結果を `artifacts/predictions.json` に保存しており、実行時にモデルサービングを呼び出さない。ナレッジ検索も同様に、`data/knowledge/knowledge_base.json` を直接読み込むのみでVector Searchを使わない。
- **合成データと事前計算済み予測の場所**：生データは `data/`、統合済み顧客360・予測・事前生成済み推奨は `artifacts/`（本README 5節・6節）。いずれもGit管理下でリポジトリに含まれる。
- **Databricks接続を有効化する場合の設定箇所**：データモードは `DATABRICKS_SERVER_HOSTNAME` / `DATABRICKS_HTTP_PATH` / `DATABRICKS_TOKEN`（本README 12節）。実LLMは `LLM_ENDPOINT_URL` / `LLM_API_KEY` / `LLM_MODEL` / `LLM_TIMEOUT_SECONDS` / `LLM_MAX_RETRIES`（本README 6節）。いずれもDatabricks Appsのアプリ設定（環境変数またはリソース）から注入する想定で、コードへ直接記載しない。
- **デモモードと本番想定の違い**：デモモードは合成データ・事前計算済み予測・ファイルベースの判断保存を使う。本番相当では、Databricks SQL/Unity Catalogからの実データ取得、実LLMエンドポイントの常時利用、Databricks側の判断保存先（Delta テーブル等）への書き込みに置き換える設計を、差し替え境界（`backend/services/data_source.py`, `backend/services/decision_store.py`）として用意している（実装はいずれも未実施）。

## 15. Databricks Appsへのデプロイ手順

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

## 16. API一覧

| メソッド・パス | 内容 | 備考 |
| --- | --- | --- |
| `GET /api/health` | 疎通確認 | `{"status": "ok"}` を返す |
| `GET /api/metadata` | アプリ全体のメタ情報 | `data_mode`, `model_mode`, `customer_count`, `updated_at` を含む |
| `GET /api/customers` | 本日の優先顧客一覧 | 顧客360と予測をcustomer_idで結合し、休眠確率の降順で返す |
| `GET /api/customers/{customer_id}` | 顧客360＋休眠予測の詳細 | 該当顧客が無ければ404（Japanese `detail` メッセージ） |
| `GET /api/customers/{customer_id}/recommendation` | 次アクション候補 | 要約・候補（最大3件）・理由・注意事項・参照元・生成方式を返す |
| `POST /api/customers/{customer_id}/decision` | 判断（承認／修正／見送り）の保存 | `decision_id`, `decided_at` を付与して返す |
| `GET /api/feedback-summary` | フィードバック概要 | 承認/修正/見送り件数、生成方式別件数、直近の判断一覧、施策後の反応・利用再開サンプル |

`/api/customers` と `/api/customers/{customer_id}` は共通のレスポンス envelope（`data_mode`, `model_mode`, `updated_at`）を持つ。合成データ・予測結果が未生成の場合は503を返し、`scripts/generate_demo_data.py` → `scripts/prepare_customer360.py` → `scripts/train_model.py` の実行を促すメッセージを含む。

`recommendation` エンドポイントは `generation_mode` / `generation_mode_label`（本README 6節）を必ず含む。`decision` エンドポイントのリクエストボディは `decision`（`approved` / `modified` / `skipped`）、`selected_action`、`modified_text`、`comment`、`generation_mode`、`model_version` を受け付ける（いずれも `selected_action` 以降は任意）。

`feedback-summary` エンドポイントの `sample_outcomes` は、代表顧客6名分の`customer_id`・`display_name`・`campaign_status`・`customer_response`・`usage_recovery_status`・`observed_at`・`is_sample: true`・`recommended_next_action`（`type`/`label`/`reason`/`next_review_timing`）に加え、該当顧客の実際の最新判断があれば`decision`・`selected_action`・`comment`・`decided_at`（無ければ全てnull）を含む。レスポンス直下の`improvement_summary`（`expand_candidates`/`review_candidates`/`next_hypothesis`、対象が無ければ`null`）は全顧客の推奨アクションを集計した全体サマリーである（本README 6節「フィードバックループ」「次の改善アクション」参照）。

## 17. アプリの使い方（Phase 1〜6時点）

Phase 1〜4を通じて、Layer 1〜4の一連の業務フロー（Step①〜⑥）が一画面で完結します。画面各所の見出しには①〜⑥の番号を付け、デモを進める順序がひと目でわかるようにしています。

- ヘッダー：アプリ名、データモード（`合成データ（demo）` / `Databricks接続`）、モデルモード（`事前計算済み予測` / `実学習モデル`）、最終更新時刻。この4項目は常時ヘッダーで確認できる
- 左「① 本日の優先顧客」：休眠確率の降順に並んだ顧客リスト。リスク帯は色・アイコン・文字ラベルの3つで示し、色だけに依存しない。クリックで選択する
- 中央上「② 顧客360」：選択顧客のEC・QR決済/カード利用推移グラフ、利用サービス数（前期との比較）、最終利用日、問い合わせ件数、データソース一覧
- 中央下「③ 休眠リスク」：リスク帯、休眠確率、主要理由（最大3件、グラフの数値と一致）、モデルバージョン・推論日時
- 右「④ 次のアクション」：顧客状況の要約、アクション候補（最大3件、理由付き）、注意事項、参照元（社内ナレッジ文書）、生成方式（`LLM生成` / `事前生成済みLLM回答` / `デモ用ルールベース生成`）
- 右「⑤ 承認・修正・見送り」：④と同じパネル内で、アクションを選択し承認・修正・見送りを選び、コメントを添えて保存する。保存後は完了表示に切り替わる（判断保存先に書き込めない場合は「一時保存です」という警告も表示する。本README 13節）
- 下部「⑥ フィードバック概要」：承認・修正・見送りの件数、直近の判断一覧（生成方式込み）、施策後の反応・利用再開のデモ用サンプル（代表顧客6名。実際の判断があれば同じ行に反映される）（判断が一時保存の場合はここにも警告を表示する。自動再学習が未実装であることの明記は、利用者の依頼により画面から削除済み。本README 17節「本番化境界パネルの削除について」参照）

いずれかのAPI呼び出しが失敗した場合も、失敗した領域だけが日本語のエラーメッセージに切り替わり、他の領域は操作を継続できる（画面全体はクラッシュしない）。

### 本番化境界パネルの削除について（デプロイ後の変更）

実際にDatabricks Apps上へデプロイした後、利用者からの明示的な依頼により、最下部にあった折りたたみパネル「デモ構成／本番化時に追加する事項」と、フッターの一文（「判断・施策結果を次の分析・モデル・施策改善へ戻す設計です。実際の自動再学習は本番化時に追加します。」）を画面から削除した（`frontend/src/App.tsx`）。

この削除は、DEMO_SPEC.md 15節「画面に表示する本番化境界」およびCLAUDE.md 9項「実装していない本番機能を、実装済みに見せない」という明示の要件と衝突する旨を利用者へ提示したうえで、それを承知のうえで削除するという明確な指示を受けて実施したものである。本README 27節「最終受け入れチェック」の「本番未実装機能が明示される」の判定は、この変更以降は満たされていない。

当初、「⑥ フィードバック概要」パネル内の「本番化時に追加：承認・修正・見送りの記録は集計に反映されますが、実際の自動再学習・自動施策改善は本番化時に追加する予定です。」という一文（`backend/services/feedback_service.py` の`FEEDBACK_NOTE`）は削除対象に含めていなかったが、その後の利用者の依頼により`frontend/src/components/FeedbackSummaryPanel.tsx`からもこの表示を削除した。さらにその後、この文言がAPIレスポンス（`GET /api/feedback-summary`の`note`フィールド）には残り続けている点についても利用者から削除の依頼があり、`backend/services/feedback_service.py`の`FEEDBACK_NOTE`／`STORAGE_NOT_PERSISTED_NOTE`定数と`note`フィールド自体を削除した（`backend/models/schemas.py`の`FeedbackSummaryResponse`、`frontend/src/types.ts`からも`note`フィールドを削除し、対応するテスト`test_feedback_summary_notes_auto_retraining_is_not_implemented`も削除した）。**この時点で、本番化境界に関する明示はUI・APIのいずれにも一切残っていない。** なお`persisted`／`storage_mode`フィールド（Phase 5で追加した判断保存の永続化状況の表示）はこれとは別の目的のため削除対象にしておらず、引き続きAPI・UIに残っている。

## 18. 実装上の仮定

- 仮定（Phase 6で変更）：当初はフロントエンドのビルド成果物（`frontend/dist`）を通常の開発コミットではGit管理対象外とし、デプロイ時のみビルド済みフォルダーとして同期する方針だったが、実際にDatabricks Reposと連携したDatabricks Appsへデプロイした際、`FrontendBuildMissingError`で起動が失敗することを確認した。Databricks ReposがGit管理下のファイルしか同期しないためである。この実機確認を受け、`frontend/dist` を`.gitignore`の除外対象から外し、Git管理下に含める方針へ変更した。
- 理由：Databricks Reposを使ったデプロイ方式を実際に採用しているため、ビルド成果物をコミットしないと本番デプロイ自体が機能しない。ビルド成果物のコミットはソース差分管理上望ましくないが、確実に動作させることを優先した。Databricks CLIでの手動同期（`frontend/dist`をGit管理外のままにする方式A）を使う場合はこの限りではない（本README 9節）。
- 本番で確認する事項：フロントエンドのコードを変更するたびに、`frontend/dist` を再ビルドしてコミットし忘れていないか確認する（`scripts/prepare_deploy.sh`実行後、`git status`で`frontend/dist`の差分有無を必ず確認する運用が望ましい）。CI/CDパイプラインを導入する場合、コミット前に自動でビルド・差分確認するフックを検討する。

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

- 仮定：判断保存は既定でリポジトリ直下の `runtime/decisions.json`（Git管理外）へのファイル書き込みとする。Databricksデータモード（`DATABRICKS_SERVER_HOSTNAME` 等が設定済み）の場合でも、Databricks側の保存先接続は未実装のため、警告ログを出したうえで同じファイルストレージへフォールバックする。書き込み先ディレクトリが読み取り専用等で書き込めない場合は、さらにプロセス内メモリへフォールバックし、`persisted: false` をAPI・UIへ返す（Phase 5、本README 13節）。
- 理由：DEMO_SPEC.mdの要件は「永続ストレージが未設定でも動くこと」であり、Databricks Free Edition環境での確実な動作を優先した。Databricks Apps環境ではコンテナのファイルシステムが読み取り専用・再起動で消去される場合があるため、書き込み失敗を例外にせず利用者に状況を明示する設計とした。Databricks側の実装（Delta テーブルへの書き込み等）は接続方式の検証が必要なため、本フェーズのスコープ外とした。
- 本番で確認する事項：Databricks側の判断保存先（Delta テーブル等）を用意し、`backend/services/decision_store.py` の `_get_databricks_store` を実装に置き換える。インメモリフォールバックが常用される環境であれば、永続化されたキューやオブジェクトストレージへの書き込みも検討する。

- 仮定：判断保存の書き込み可否は、リクエストのたびに一時ファイルの作成・削除で軽量に確認する（`_is_directory_writable`）。書き込み不可と判定された場合のインメモリストア（`InMemoryDecisionStore`）は、プロセス内で共有インスタンスとして扱い、直前に保存した判断がその後の一覧取得に反映されるようにする。
- 理由：ファイルストレージとインメモリストアの内容を都度マージする実装は複雑になり、本フェーズの検証目的（書き込み失敗時にAPI自体を失敗させないこと）に対して過剰と判断した。
- 本番で確認する事項：実運用でファイルシステムの書き込み可否が頻繁に変化する場合、書き込み成功時に記録したファイル内容とインメモリ分の統合方法を検討する。

- 仮定：ルールベース生成が提案するアクションは、DEMO_SPEC.mdが例示する5種類（EC再利用の案内／QR決済の利用メリット案内／カード利用特典の案内／複数サービスをまたぐ軽量なポイント施策／施策を行わず経過観察）に固定し、それ以外の自由記述アクションは生成しない。
- 理由：推奨アクションが業務方針から逸脱しないことを構造的に保証するため（自由記述だと過度なインセンティブ等が紛れ込むリスクがある）。
- 本番で確認する事項：実際の施策カタログが追加・変更された場合、`backend/services/rule_based_generator.py` のアクション定数とナレッジ文書（`data/knowledge/knowledge_base.json`）を合わせて更新する。

## 19. 失敗時の対処

`frontend/dist/index.html` が見つからずproductionモードで起動が失敗した場合：

1. ログに出力された `frontend/dist/index.html が見つかりません。scripts/prepare_deploy.sh を実行してから再デプロイしてください。` を確認する。
2. ローカルで `bash scripts/prepare_deploy.sh` を実行し、型チェック・ビルド・テストがすべて成功することを確認する。
3. 生成された `frontend/dist` を含むフォルダーを、Databricksワークスペースの配置先へ再同期する。
4. Databricks Appsを再デプロイし、アプリログと `/api/health`・画面表示の両方を再確認する。

## 20. Databricks Appsへのデプロイ実行状況（Phase 6）

### 実行結果：この開発環境からの実デプロイは未実施

Phase 6の作業環境（本リポジトリの開発・検証を行っているサンドボックス環境）には、次の理由により実際のDatabricks Appsへのデプロイを実行できなかった。

- 環境変数 `DATABRICKS_HOST` / `DATABRICKS_TOKEN` は設定されていたが、この環境からDatabricksワークスペース本体（`dbc-*.cloud.databricks.com`）への外向きネットワーク接続は、ネットワークポリシーにより遮断されている。
- 実際に確認したコマンドと結果：

  ```text
  $ curl -sS -o /dev/null -w "HTTP_CODE:%{http_code}\n" \
      "https://dbc-74bfd917-30ed.cloud.databricks.com/api/2.0/clusters/list" \
      -H "Authorization: Bearer $DATABRICKS_TOKEN"
  curl: (56) CONNECT tunnel failed, response 403
  ```

- この結果は「認証情報が無効」ではなく、この開発環境の通信ポリシーによる接続遮断（プロキシがCONNECTトンネルを403で拒否）である。Databricks CLIやREST APIを使った実際のワークスペース操作（アプリ作成・コードのアップロード・起動確認）は、いずれもこの制約により本セッションから実行できない。
- したがって、本README「9. Databricks Appsへの配置方法」「15. Databricks Appsへのデプロイ手順」に記載した手順は、**この環境で実際に最後まで実行して検証したものではなく**、コード・設定内容から導いた手順書である。手順書自体の正確性（`app.yaml` の記法、ポート解決、SPAフォールバック、API疎通等）はローカルでのproductionモード相当の起動確認（本README「22. デモ実演用の操作手順」直前の検証、および22節の実行ログ）で担保しているが、実際のDatabricksワークスペースUI操作・実際のアプリ作成・実際のURL発行は未確認である。

### 利用者がDatabricksワークスペースで実行する手順

ネットワークアクセス・認証情報を持つ利用者は、以下の手順でデプロイを実行できる（本README「9節」「15節」の手順書と同一。ここに要点のみ再掲する）。

1. 手元の開発端末またはCI環境で `bash scripts/prepare_deploy.sh` を実行し、`frontend/dist` を含むビルド成果物一式を用意する（本手順自体はこのセッションで実行し、72件のテストと本番相当ビルドの成功を確認済み。本README 8節・22節参照）。
2. `app.yaml` / `requirements.txt` / `backend/` / `frontend/dist/` を含むフォルダーを、Databricksワークスペース（Databricks CLIの `databricks sync` や、ワークスペースUIのファイルアップロード等）へ同期する。
3. Databricks Appsで新規アプリを作成し、同期したフォルダーをソースとして指定する。
4. 必要であれば、Databricks SQLウェアハウス等のリソースをアプリへ関連付け、`DATABRICKS_SERVER_HOSTNAME` / `DATABRICKS_HTTP_PATH` / `DATABRICKS_TOKEN`（未設定ならdemoモードで起動する）を設定する。
5. デプロイを実行し、アプリのログで起動成功（`Uvicorn running on ...`）を確認する。
6. 本README「22. デモ実演用の操作手順」の確認項目（アプリ表示・`/api/health`・顧客一覧・顧客詳細・推奨生成・判断保存・フィードバック概要）を、発行されたアプリURLに対して実施する。

### アプリURL

未デプロイのため、アプリURLは存在しない。デプロイ後は、Databricks Appsのアプリ詳細画面に表示されるURLをここに記録することを推奨する。

## 21. アプリ停止時の再起動・再デプロイ手順（Free Edition）

Databricks Free EditionのDatabricks Appsは、一定時間アクセスが無い場合等にアプリが停止する場合がある。本デモは次の設計により、停止・再起動を挟んでも合成データや事前計算済み予測を失わずに復旧できる。

### 再起動時に失われないもの

- `data/`（合成データ）・`artifacts/`（顧客360・予測・事前生成済み回答）はいずれもGitコミット対象であり、アプリの起動コードが読み込むファイルはワークスペースへ同期済みのフォルダー内に存在する。再起動時に再生成する必要はない。
- 判断保存が通常のファイル書き込み（`storage_mode: "file"`）で成功している場合、`runtime/decisions.json` はコンテナの永続ディスク上に存在する限り再起動後も保持される。

### 再起動時に失われる可能性があるもの

- 判断履歴（`runtime/decisions.json`）は`.gitignore`対象であり、Databricks Apps側のコンテナが再起動時にファイルシステムを初期化する構成の場合は失われる。これは`persisted`/`storage_mode`フィールドを通じてUIに明示される仕組みで吸収する設計としている（本README 13節）。この「再起動でファイルシステムが初期化されるかどうか」自体は、実際のDatabricks Apps環境で確認が必要な事項であり、この開発環境では確認できていない。

### 再起動手順

1. Databricks Appsのアプリ管理画面からアプリの状態を確認する。停止している場合は「起動」または同等の操作を行う。
2. 起動後、`/api/health` が200を返すこと、ブラウザでアプリを開いてUIが表示されることを確認する。
3. `/api/metadata` で `data_mode` / `model_mode` / `customer_count` が想定通りであることを確認する（想定：`data_mode: "demo"`、`customer_count: 60`、Databricks SQL接続設定済みの場合のみ`data_mode: "databricks"`）。
4. フィードバック概要（`/api/feedback-summary`）を確認し、`persisted: false` が返る場合は、判断保存が一時的な状態であることを画面の警告表示で利用者に伝える（アプリコード側の対応は実装済み。本README 13節）。

### コードを変更した場合の再デプロイ

1. 変更後、`bash scripts/prepare_deploy.sh` を再実行し、型チェック・単体テスト・ビルド・Pythonテストがすべて成功することを確認する。
2. 生成された最新の `frontend/dist` を含むフォルダーをDatabricksワークスペースへ再同期する。
3. Databricks Appsを再デプロイする。
4. 本README「22. デモ実演用の操作手順」の確認項目を再実施する。

## 22. デモ実演用の操作手順（短縮版）

顧客維持担当者向けの本番画面の詳しい説明は本README「17節」に記載している。ここでは、デモを実演する担当者向けに、必要な操作だけを短く示す。

1. アプリを開く。ヘッダーで「合成データ（demo）」等の表示を確認し、これがデモ用データであることを一言添える。
2. 左「① 本日の優先顧客」から、高リスク（赤・「高リスク」ラベル）の顧客を1人クリックする。⑥で施策後の反応サンプルまで一気通貫で見せたい場合は、下記「実演で見せると効果的な代表顧客」の6名（`C059`, `C017`, `C015`, `C045`, `C010`, `C031`）のいずれかを選ぶとよい。
3. 中央上「② 顧客360」で、EC・QR決済/カードの利用推移グラフが右肩下がりであることを指し示す。
4. 中央下「③ 休眠リスク」で、休眠確率とリスク帯、主要理由（最大3件）を読み上げる。理由の数値がグラフと一致することを説明する。
5. 右「④ 次のアクション」で、要約・アクション候補・理由・注意事項・参照元・生成方式（`LLM生成` / `事前生成済みLLM回答` / `デモ用ルールベース生成` のいずれか）を確認する。
6. 「⑤ 承認・修正・見送り」で、候補を1つ選び「承認」を押し、任意でコメントを入力して「判断を保存」を押す。保存完了表示に切り替わることを見せる。
7. 下部「⑥ フィードバック概要」で、件数と直近の判断一覧に今保存した判断が反映されていることを確認する。デモで実装済みの範囲と本番化時に追加する範囲の違いを口頭で補足したい場合は、本README 24節「本番化時に追加する設計一覧」を参考に説明する（画面上の折りたたみパネルは利用者の依頼により削除済み。本README 17節参照）。
8. 続けて「施策後の反応と利用状況」を見せ、手順6で承認した顧客の行に自分が選んだ判断が表示されていることを指し示す。**画面上には表示されないため、口頭で「施策後の反応・利用状況はデモ用のサンプルであり、担当者判断欄のみ実際にこの画面で保存したデータである」ことを必ず補足する**（本README 6節「サンプルである旨の画面表示を削除した経緯」参照）。最後に、判断→施策→反応→利用再開→次の顧客選定・モデル・施策改善へ戻るという改善ループの全体像で締めくくる。

このデモは10分程度を想定している。各ステップの見出しに①〜⑥の番号を付けているため、口頭説明とスクロール操作が対応しやすい。

### 実演で見せると効果的な代表顧客（固定シナリオ）

事前生成済みLLM回答（本README 6節）を持つ6顧客は、実LLM未設定・未接続の環境でも「事前生成済みLLM回答」として質の高い推奨文を確実に表示できるため、デモの主役として推奨する。

| customer_id | リスク帯 | 休眠確率（目安） | 用途 |
| --- | --- | --- | --- |
| C059 | 高 | 0.93 | 高リスクの代表例。QR決済が完全停止、EC・カードも低下 |
| C017 | 高 | 0.92 | 高リスクの代表例（複数サービス低下の別パターン） |
| C015 | 中 | 0.65 | 中リスクの代表例 |
| C045 | 中 | 0.62 | 中リスクの代表例（別パターン） |
| C010 | 低 | 0.32 | 低リスクの代表例（横ばい・増加傾向） |
| C031 | 低 | 0.29 | 低リスクの代表例（別パターン） |

## 23. デモ失敗時のバックアップ手順

デモ実施中にネットワーク障害・Databricks側の一時的な不調・実LLM未接続などが発生しても、Step①〜⑥のデモフローを止めないための多段バックアップを実装済みである。

### バックアップの構成

| 層 | 内容 | 保存場所 | Git管理 |
| --- | --- | --- | --- |
| 合成データ | EC・QR決済・カード・銀行・過去施策・問い合わせの生データ | `data/` | 対象 |
| 事前計算済み顧客360 | customer_idで統合済みの顧客像 | `artifacts/customer360.json` | 対象 |
| 事前計算済み予測結果 | 休眠確率・リスク帯・予測理由・モデルバージョン | `artifacts/predictions.json`, `artifacts/model_metadata.json` | 対象 |
| 事前生成済みLLM回答 | 6顧客分の実際のLLM品質の推奨文（本README 22節） | `artifacts/pre_generated_recommendations.json` | 対象 |
| ルールベースの推奨結果 | 全60顧客をカバーする決定論的フォールバック | `backend/services/rule_based_generator.py`（実行時に生成、保存不要） | コード |
| 代表顧客の固定シナリオ | 高・中・低リスクを確実に見せられる6顧客のID | 本README 22節の表 | ドキュメント |
| API失敗時の安全なフォールバック | 各パネルを`ErrorBoundary`で分離し、失敗した領域のみ日本語エラー表示に切り替え | `frontend/src/components/ErrorBoundary.tsx` | コード |

これらはすべて本デモがLayer1〜3で採用している「実データ・実LLM → 事前計算済み・事前生成済み → 決定論的ルールベース」という同じ多段フォールバック思想の一部であり、Phase 6で新規に作ったものではなく、既存の設計（本README 5節・6節・13節）をバックアップの観点で整理し直したものである。

### 復旧手順（症状別）

**画面が真っ白、または起動していない**
1. Databricks Appsのログを確認する。`frontend/dist/index.html が見つかりません` と出ている場合は、本README「19. 失敗時の対処」の手順に従う。
2. それ以外のエラーの場合、アプリを再起動する（本README 21節）。

**顧客一覧・顧客詳細が503を返す**
1. `artifacts/customer360.json` / `artifacts/predictions.json` が同期先フォルダーに存在するか確認する（コミット漏れ・同期漏れの可能性）。
2. 存在しない場合、`scripts/generate_demo_data.py` → `scripts/prepare_customer360.py` → `scripts/train_model.py` を実行して再生成し、`artifacts/` を含めて再デプロイする。

**推奨アクションが表示されない、またはエラーになる**
1. ルールベース生成は入力データのみから決定論的に組み立てるため原理上必ず成功する。エラーが出ている場合は顧客360・予測データ自体の欠落を疑う（上記「顧客一覧が503」の手順を確認）。
2. 実LLM接続を設定している場合、LLM側の障害は自動的に事前生成済み回答→ルールベースへフォールバックするため、利用者操作は不要（表示される生成方式バッジで実際に使われた方式を確認できる）。

**判断が保存できない、保存してもフィードバック概要に反映されない**
1. レスポンスの `persisted` フィールドを確認する。`false` の場合は書き込み先が読み取り専用であることを示す（本README 13節）。デモの続行自体は可能（一時保存のまま操作を続けられる）だが、アプリ再起動で消える可能性がある旨を口頭で補足する。
2. コンテナの永続ディスク設定を確認し、書き込み可能なパスへ変更できないか検討する（本番化時の対応、本README 26節）。

**ネットワーク・電源障害などでライブデモ自体が続行不能な場合**
1. 本README「22節」のスクリーンショット代わりに、ローカル環境またはあらかじめ録画したデモ映像（用意している場合）で説明を継続する。
2. 事前生成済み回答を持つ6顧客（本README 22節の表）を優先的に見せることで、実LLM接続やネットワークに依存しない説明が可能である。

## 24. 本番化時に追加する設計一覧

DEMO_SPEC.md「13. 説明のみとする本番機能」「15. 画面に表示する本番化境界」と一致させたうえで、本リポジトリのどの差し替え境界が対応するかを整理する。

| 本番化時に追加する項目 | 対応する差し替え境界（現状の実装） |
| --- | --- |
| Databricks SQL / Unity Catalogからの実データ取得 | `backend/services/data_source.py`（現状はdemoモードへ常時フォールバック。実装は未着手） |
| 実LLMエンドポイントの常時利用 | `backend/services/llm_client.py` / `backend/config.py` の `resolve_llm_config()`（呼び出し自体は実装済み。実際のエンドポイント形式への調整が必要。本README 18節） |
| Databricks側の判断保存先（Delta テーブル等） | `backend/services/decision_store.py` の `_get_databricks_store`（現状は未実装のスタブ。ファイル→インメモリへフォールバック） |
| サービス間の高度なID解決・CDC | 未実装（説明のみ。DEMO_SPEC.md 13節） |
| 行・列レベルアクセス制御・PIIマスキング | 未実装（説明のみ） |
| 監査ログの詳細設計 | 未実装（現状はエラー種別・匿名customer_idのみを記録する簡易ログ。本README 13節） |
| モデル承認・ドリフト監視・自動再学習 | 未実装（UI・API双方の明記は利用者の依頼により削除済み。本README 17節） |
| RAG品質評価 | 未実装（社内ナレッジ6件を全件参照する簡易実装のみ） |
| 外部施策システムとの本番API連携 | 未実装（判断結果の保存のみ。自動配信は行わない） |
| 施策後の反応・利用再開の実データ取り込み、効果の因果推論 | 未実装（`artifacts/sample_campaign_outcomes.json`による固定サンプル表示のみ。本README 6節「フィードバックループ」） |
| 障害復旧とSLA | 未実装（本README 21節の再起動手順は運用の目安であり、SLAを保証するものではない） |
| CI/CDによるビルド・デプロイ自動化 | 未実装（`scripts/prepare_deploy.sh` は手動実行前提。本README 18節） |

## 25. 既知の制約一覧

- 合成データは60顧客のみであり、実際の顧客基盤の規模・分布を反映していない。
- 休眠リスクモデルは実績の解約・休眠ラベルを持たないため、業務ルールから疑似ラベルを生成して学習している（本README 5節）。モデル評価値は小規模な合成データ上の参考値であり、本番精度を示すものではない。
- 事前生成済みLLM回答は60顧客中6顧客のみで、対象外の顧客はルールベース生成にフォールバックする（本README 18節）。
- 実LLMエンドポイントのリクエスト・レスポンス形式はOpenAI互換のchat completions形式を仮定しており、実際に接続するエンドポイントの形式によっては `backend/services/llm_client.py` の調整が必要（本README 18節）。
- 判断保存は既定でファイルベース（`runtime/decisions.json`）であり、Databricks側の実際の永続化先（Delta テーブル等）への接続は未実装（本README 13節・24節）。
- 書き込み不可時のインメモリフォールバックは、アプリプロセスの再起動で内容が失われる。ファイル保存分とインメモリ保存分を統合する仕組みも未実装（本README 18節）。
- 本デモの実行環境（このセッション）から実際のDatabricksワークスペースへのネットワーク接続ができないため、Databricks Apps上での実デプロイ・実起動・実際の読み取り専用ファイルシステムや再起動シナリオを、この開発環境からは確認できていない（本README 20節・26節）。
- CORS・入力検証・ログ出力の点検は本リポジトリのコードレベルで実施したものであり、実際のDatabricks Appsのネットワーク境界・プロキシ設定・監査要件は別途確認が必要。
- 自動配信・自動再学習・外部施策システム連携は実装しておらず、フィードバック概要はあくまで人手による次回参照用の記録である。

## 26. デモ前チェック・データ品質テスト結果（Phase 1〜6時点で確認済みの項目）

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
- [x] 自動配信・自動再学習を実装しておらず、フィードバック概要に「本番化時に追加」と明記している（Phase 4時点。※Databricks Appsデプロイ後、利用者の依頼によりUI・API双方から明記を削除。本README 17節参照）
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

### ポート・ホスト解決（Phase 1、`backend/tests/test_config.py` で確認済み）

- [x] `DATABRICKS_APP_PORT` が設定されている場合は最優先される（`test_resolve_port_prefers_databricks_app_port_over_others`）
- [x] `DATABRICKS_APP_PORT` 未設定時は `UVICORN_PORT` へ移行する（`test_resolve_port_prefers_uvicorn_port_over_port`）
- [x] さらに未設定時は `PORT` へ移行する（`test_resolve_port_uses_port_when_only_port_set`）
- [x] すべて未設定の場合は既定値8000になる（`test_resolve_port_defaults_to_8000`）
- [x] 空文字列の環境変数は未設定として扱われる（`test_resolve_port_ignores_empty_string_values`）
- [x] `UVICORN_HOST` 未設定時は `0.0.0.0` になる（`test_resolve_host_defaults_to_zero_zero_zero_zero`）

### テスト・堅牢化（Phase 5）

- [x] SPAフォールバック：未知の非APIパスは `index.html` を返し、`/api/*` の404はJSONのまま（`test_unknown_non_api_path_falls_back_to_spa_index`, `test_unknown_api_path_stays_json_404_not_spa_index`）
- [x] 静的ファイル配信とAPIルートが競合しない（同上、`/api/health` 等が静的マウントに奪われないことを確認）
- [x] 判断保存先が書き込み不可の場合、インメモリストレージへ自動フォールバックし、`persisted: false` を返す（`backend/tests/test_decision_store_fallback.py`。権限依存の回避策として、親コンポーネントがファイルであるパスを使った privilege-independent なテストで確認）
- [x] インメモリフォールバックはプロセス内で共有され、直前の保存内容が一覧取得に反映される
- [x] APIの入力検証：`decision` は許可値のみ（422）、コメント等の文字数上限超過は422
- [x] ログに秘密情報・個人情報を出力していないことをコード全体で確認（LLM呼び出し失敗時は例外の型名のみ記録）
- [x] CORSミドルウェアを導入していないこと（フロントエンド・バックエンドは常に同一オリジン）を確認
- [x] 依存関係（`requirements.txt`, `scripts/requirements-scripts.txt`, `frontend/package.json`）に未使用のものが無いことを確認
- [x] フロントエンド単体テスト11件（Vitest + Testing Library）が全件成功する：`RiskBadge`（色以外の手段でのリスク表示）、`CustomerListPanel`（一覧表示・選択・`aria-pressed`）、`RecommendationPanel`（表示・保存成功・保存失敗時の日本語エラー・非永続時の警告表示）
- [x] `bash scripts/prepare_deploy.sh` にフロントエンド単体テストを組み込み、型チェック・テスト・ビルド・Pythonテストが一括で成功する
- [ ] Databricks Apps上での実際の読み取り専用ファイルシステム・再起動シナリオの確認（この修正では未実施、ワークスペースアクセスが必要）

### デプロイ・最終受け入れ（Phase 6）

- [x] `python -m pytest backend/tests -v` が72件成功・1件スキップ（root権限のためchmodベースの読み取り専用テストが自己スキップ。権限に依存しない代替テストで同等の挙動を確認済み）
- [x] `bash scripts/prepare_deploy.sh` が最後まで成功する（型チェック・フロントエンド単体テスト11件・ビルド・Pythonテスト72件を含む）
- [x] 未使用コード・未使用の依存関係が無いことを専用の調査で確認済み（削除対象なし）
- [x] `APP_ENV=production` かつビルド済み `frontend/dist` が存在する状態でローカル起動し、`/`（UI表示）・`/api/health`・`/api/metadata`・`/api/customers`・`/api/customers/{id}`・`/api/customers/{id}/recommendation`・`POST /api/customers/{id}/decision`・`/api/feedback-summary` を実際に呼び出し、想定通りのレスポンスを確認済み（本README 20節に記載の通り、これはローカルでのproductionモード相当の検証であり、実際のDatabricks Apps上での確認ではない）
- [x] ブラウザ（Playwright）で実際に画面を開き、顧客選択→顧客360→休眠リスク→次アクション→判断保存→フィードバック概要反映までの一連の操作が成功することをスクリーンショットで確認済み
- [ ] 実際のDatabricksワークスペースへの接続・デプロイ・起動確認：この開発環境からDatabricksワークスペース本体へのネットワーク接続ができないため未実施（本README 20節に理由を記載）

### 施策後の反応・利用再開サンプル（フィードバックループ追加分）

- [x] サンプル結果（`artifacts/sample_campaign_outcomes.json`）が固定され、再取得しても変化しない（`test_sample_outcomes_are_fixed_and_flagged_as_sample`）
- [x] サンプルの`customer_id`が実在する顧客と一致する（`test_sample_outcomes_customer_ids_exist_in_customer360`）
- [x] 各サンプルに`is_sample: true`が含まれる（同上）
- [x] 判断記録が無い状態でもフィードバック概要が取得でき、`sample_outcomes`の`decision`は`null`になる（`test_feedback_summary_starts_empty`）
- [x] サンプル対象顧客に実際の判断を保存すると、同じ顧客の行に担当者判断（`decision`/`selected_action`/`comment`/`decided_at`）が反映される。反応・利用再開自体は変化しない（`test_sample_outcome_reflects_saved_decision_for_same_customer`）
- [x] 既存の`/api/feedback-summary`のフィールド（`total_decisions`等）が引き続き揃っており、後方互換性が保たれている（`test_sample_outcomes_do_not_break_existing_feedback_summary_fields`）
- [x] フロントエンドで「施策後の反応と利用状況」がサンプルである旨の画面表示：追加当初→利用者の依頼で削除→次の推奨判断機能の追加時に利用者の依頼で再度表示、という経緯を経て、現時点では「施策後の反応、利用状況、次の推奨判断は、改善ループを説明するためのデモ用サンプルです。」という注記が画面に表示されている（本README 6節「サンプルである旨の画面表示の変遷」参照）
- [x] `反応なし`・`利用再開なし`・`観測期間中`・`施策未実施`を含む全カテゴリの表示を確認
- [x] 判断未保存時は「未対応（判断未保存）」、保存済みの場合は判断内容（選択アクション・コメント含む）を表示することを確認
- [x] サンプルデータが空でもレイアウトが崩れないことを確認
- [x] Playwrightで、顧客選択→承認保存→フィードバック概要反映→サンプル行への反映→サンプル注記の表示、までの一連の流れを確認（幅375pxのモバイル表示でもカードが1列に収まり文字が重ならないことをスクリーンショットで確認）
- [x] `python -m pytest backend/tests`、`npm run typecheck`、`npm run test`、`npm run build`、`bash scripts/prepare_deploy.sh` が全件成功

### 次の改善アクション（推奨アクション・改善サマリー追加分）

- [x] 反応あり・利用再開ありで「類似顧客へ展開」が返る（`test_engaged_and_recovered_returns_expand`）
- [x] 反応あり・利用再開なしで「オファー内容を変更」が返る（`test_engaged_and_not_recovered_returns_change_offer`）
- [x] 反応なし・利用再開なしで「接触チャネルを変更」が返る（`test_not_engaged_and_not_recovered_returns_change_channel`）
- [x] 見送りで、反応・利用再開の内容に関わらず「対象顧客の条件を見直す」が返る（`test_skipped_decision_returns_review_targeting_regardless_of_outcome`）
- [x] 観測期間中で「継続観測」が返る（`test_observing_period_returns_continue_observation`）
- [x] 未知の値・欠損値でもAPIが500にならず、安全な既定値を返す（`test_unknown_values_do_not_raise_and_return_fallback`、`test_missing_values_do_not_raise`）
- [x] 同じ入力では毎回同じ推奨アクションになる（`test_same_input_returns_same_result_every_time`）
- [x] 全体改善サマリーは対象0件の場合すべて`null`を返し、対象がある場合は3項目とも文章を生成する（`test_build_improvement_summary_returns_none_fields_when_no_outcomes`、`test_build_improvement_summary_populates_fields_when_outcomes_exist`）
- [x] `GET /api/feedback-summary`の`sample_outcomes`各要素に`recommended_next_action`が含まれる（`test_sample_outcomes_include_recommended_next_action`）
- [x] 判断保存後、対象顧客の`recommended_next_action`が更新される（`test_skipped_decision_updates_recommended_next_action_to_review_targeting`）
- [x] `improvement_summary`フィールドが期待するキーを持つ（`test_feedback_summary_includes_improvement_summary_with_expected_keys`）
- [x] フロントエンドで次の推奨判断・理由・次回確認が表示される（`FeedbackSummaryPanel.test.tsx`）
- [x] 今回の改善ポイント（継続・展開候補／見直し候補／次回検証する仮説）が表示される。対象が無い場合は「現時点では十分な結果がありません。」の空状態文言を表示する
- [x] サンプルである旨の注記、およびStep 6末尾の締めくくり文が重複なく1回ずつ表示される
- [x] Playwrightで、顧客選択→承認保存→サンプル行への担当者判断反映→次の推奨判断・理由・次回確認の表示→今回の改善ポイントの表示、までの一連の流れを確認（幅375pxのモバイル表示でも崩れないことをスクリーンショットで確認）
- [x] `python -m pytest backend/tests`（88件成功・1件スキップ）、`npm run typecheck`、`npm run test`（21件成功）、`npm run build`、`bash scripts/prepare_deploy.sh` が全件成功

## 27. 最終受け入れチェック（Phase 6）

Phase 6のプロンプトで示された受け入れ条件を、カテゴリごとに1項目ずつ確認した結果を記録する。

### 業務

- [x] 一人の利用者、一人の顧客、一つの判断に絞られている（画面は顧客維持担当者が1顧客を選び、承認・修正・見送りのいずれかを選ぶ構成。本README 17節）
- [x] 3課題と3アウトカムから外れていない（DEMO_SPEC.md 2節・3節の文言を画面・README・生成コンテンツのいずれにも追加改変せず使用）
- [x] 優先顧客を選べる（左「① 本日の優先顧客」、休眠確率降順）
- [x] グループ横断の顧客像を確認できる（中央上「② 顧客360」、EC・QR決済/カード・銀行の利用推移とサービス数）
- [x] 休眠リスクと理由を確認できる（中央下「③ 休眠リスク」、確率・リスク帯・理由最大3件）
- [x] 次アクションと根拠を確認できる（右「④ 次のアクション」、候補最大3件・理由・注意事項・参照元）
- [x] 人が承認、修正、見送りできる（右「⑤ 承認・修正・見送り」、自動実行なし）
- [x] 結果が改善ループへ記録される（下部「⑥ フィードバック概要」、`POST /api/customers/{id}/decision` → `GET /api/feedback-summary` で反映を確認済み。加えて施策後の反応・利用再開のデモ用サンプル表示により、判断→施策→反応→利用再開→次の分析・モデル・施策改善という改善ループの全体像を画面上で確認できる。本README 6節「フィードバックループ」参照）

### 技術

- [x] 2ソース以上を統合している（EC・QR決済・カード・銀行・過去施策・問い合わせの計6ソースをcustomer_idで統合。`artifacts/customer360.json` の `data_sources` フィールドで確認可能）
- [x] 顧客360がMLへ渡る（`scripts/train_model.py` が `artifacts/customer360.json` を入力とする）
- [x] 顧客360とML出力が推奨生成へ渡る（`backend/services/recommendation_context.py` が顧客360＋予測結果＋ナレッジを統合してコンテキストを作成）
- [x] Pythonバックエンドである（FastAPI + Uvicorn、`backend/main.py`）
- [x] React + TypeScriptフロントエンドである（`frontend/src/`、Vite）
- [x] Streamlitを使っていない（依存関係に含まれず、コード内にも参照なし）
- [x] Expressバックエンドを使っていない（Node.jsはフロントエンドビルドのみに使用。`app.yaml` の起動コマンドはPythonのみ）
- [x] Databricks Apps用構成がある（`app.yaml`、ポート・ホスト解決、SPAフォールバック）
- [x] Free Editionで安全にフォールバックする（demoモード、事前計算済み予測、判断保存のインメモリフォールバック）
- [x] 実LLM → 事前生成済み回答 → ルールベースの優先順位が実装されている（`backend/services/recommendation_service.py`、モックテストで3方式とも確認済み）
- [x] APIとUIが実際の生成方式を表示する（`generation_mode` / `generation_mode_label`、次のアクションパネルのバッジ表示）

### 表示

- [x] 日本語UI（見出し・ラベル・エラーメッセージすべて日本語）
- [x] 淡く鮮やかな配色（`frontend/src/styles/tokens.css`、白背景＋淡い青・緑・黄・赤紫）
- [x] 常識的な金額・利用頻度（生成スクリプトのデータ品質チェックで0〜500,000円の範囲、負値なしを保証。本README 26節）
- [x] 不自然なゼロや負値がない（同上、自動チェック済み）
- [x] 予測理由とデータが一致する（理由生成が顧客360の実数値から算出。本README 5節）
- [x] 生成方式とモデル方式が明示される（`model_mode`：`precomputed`/`trained`、`generation_mode`：本README 6節）
- [x] 合成データが明示される（ヘッダーの「合成データ（demo）」バッジ）
- [ ] 本番未実装機能が明示される：デプロイ後、利用者の明示的な依頼により画面下部の折りたたみパネル・フッターの一文・「⑥ フィードバック概要」内の一文（UI・APIレスポンスの`note`フィールド双方）をすべて削除したため、この時点ではUI・APIのいずれにも本番化境界の明示が一切残っておらず、条件を満たしていない（本README 17節「本番化境界パネルの削除について」参照）。本番化時に追加する設計の一覧自体は本README 24節（ドキュメント）に維持している。

### ドキュメント

- [x] READMEに利用方法がある（本README 7節・17節・22節）
- [x] READMEにDatabricks Appsへのデプロイ方法がある（本README 9節・15節・20節）
- [x] READMEに再起動・復旧方法がある（本README 21節・23節）
- [x] READMEに本番化時の追加事項がある（本README 24節）
- [x] READMEに既知の制約がある（本README 25節）

### このチェックにおける注意

上記はいずれもコードレベル・ローカル環境（productionモード相当の起動を含む）での確認であり、「Databricks Apps用構成がある」「Free Editionで安全にフォールバックする」の2項目についても、構成・コードが存在し期待通りに動作することをローカルで確認したという意味であって、実際のDatabricksワークスペース上での起動・課金・クォータ挙動を確認したものではない（本README 20節）。

## 28. 伝えること・伝えないこと

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
