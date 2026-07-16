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

## 2. 現在の実装状況（Phase 1）

Phase 1では、以下のみを実装しています。詳細な業務ロジック（顧客一覧・予測・推奨・判断保存等）はPhase 2以降で追加します。

- React + TypeScript + Vite のフロントエンド骨格（1画面、日本語ベースレイアウト、空状態表示）
- FastAPI + Uvicorn のPythonバックエンド骨格
- `/api/health`、`/api/metadata` の実装
- Databricks接続未設定でも起動する `demo` モードの設定層
- **デプロイ前ビルド方式**：Reactは事前にProduction Buildし、`frontend/dist` をPythonが配信する。Databricks Apps（`APP_ENV=production`）ではビルド成果物が無い場合に起動を失敗させ、UIが欠落したまま正常起動したように見せない
- デプロイ前準備を一括実行する `scripts/prepare_deploy.sh`
- Databricks Apps向け `app.yaml`
- ホスト・ポート解決、データモード判定、起動モード判定の単体テスト

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
│   └── prepare_deploy.sh     # デプロイ前ビルド・テストの一括実行スクリプト
├── backend/
│   ├── main.py                # FastAPIエントリーポイント（起動モード判定・Reactビルドの配信を含む）
│   ├── config.py               # ホスト・ポート・データモード・起動モード解決ロジック
│   ├── api/
│   │   └── routes.py           # /api/health, /api/metadata
│   └── tests/
│       ├── test_config.py
│       ├── test_api.py
│       └── test_deploy_modes.py  # development/productionモードの起動挙動テスト
├── frontend/
│   ├── package.json
│   ├── package-lock.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── index.html
│   ├── dist/                   # npm run build で生成（Git管理外）
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── App.css
│       ├── types.ts
│       ├── api/client.ts
│       └── styles/
│           ├── tokens.css
│           └── global.css
├── generate_ecommerce_sample_data.py   # Databricksノートブック用（Phase 1以前から存在）
└── save_bronze_delta_tables.py         # Databricksノートブック用（Phase 1以前から存在）
```

`data/`、`artifacts/` はPhase 2以降、合成データ生成・顧客360構築・モデル学習を実装する際に追加します。

## 5. ローカル開発

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

## 6. デプロイ前ビルド（Production Build）

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

## 7. Databricks Appsへの配置方法

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

## 8. 起動モード（development / production）

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

## 9. ポート・ホスト解決

Pythonサーバーは次の優先順位で起動設定を解決します（`backend/config.py`）。

```text
Host: UVICORN_HOST → 0.0.0.0
Port: DATABRICKS_APP_PORT → UVICORN_PORT → PORT → 8000
```

- Databricks Appsでは、プラットフォームが提供する `DATABRICKS_APP_PORT` を優先して使用します。
- ローカル開発では `PORT` を設定でき、未設定の場合は8000を使用します。
- `app.yaml` 側では固定ポートを指定しません（起動コマンドと `APP_ENV` のみ定義）。
- 優先順位はホスト・ポートとも `backend/tests/test_config.py` で単体テスト済みです。

## 10. データモードの解決

`backend/config.py` の `resolve_data_mode()` が、以下3つのDatabricks SQL接続用環境変数がすべて設定されている場合のみ `databricks` モードを返し、それ以外は `demo` モードにフォールバックします。

- `DATABRICKS_SERVER_HOSTNAME`
- `DATABRICKS_HTTP_PATH`
- `DATABRICKS_TOKEN`

Phase 1では実際のDatabricks SQL接続は行わず、モード判定のみを実装しています。実データ接続はPhase 2以降で追加します。

## 11. Databricks Appsへのデプロイ手順

正確な操作はワークスペースUIと利用可能な機能に合わせて確認してください。完成条件は、ローカル起動ではなくDatabricks Apps上で表示できることです。

基本手順：

1. `bash scripts/prepare_deploy.sh` を実行し、`frontend/dist` を生成する（本README 6節）。
2. ビルド済みの `frontend/dist` を含むフォルダーを、Databricksワークスペースのフォルダーまたは同期先へ配置する（本README 7節。GitリポジトリのURLから直接デプロイする方式は `frontend/dist` が欠落するため避ける）。
3. Databricks Appsでカスタムアプリを作成する。
4. アプリのソースとして、ビルド済みフォルダーを選ぶ。
5. Databricks SQLに接続する場合は、必要なDatabricksリソース（SQLウェアハウス等）をアプリへ追加し、`DATABRICKS_SERVER_HOSTNAME` / `DATABRICKS_HTTP_PATH` / `DATABRICKS_TOKEN` に相当する接続情報を設定する。未設定の場合はdemoモードで起動する。
6. `app.yaml` の `APP_ENV=production` 設定により、Python起動処理がproductionモードで動作することを確認する（`frontend/dist/index.html` が無い場合はここで起動失敗する）。
7. Python起動処理が `DATABRICKS_APP_PORT` → `UVICORN_PORT` → `PORT` → `8000` の順でポートを解決し、ホストは `UVICORN_HOST` または `0.0.0.0` を使用することを確認する（`app.yaml` の起動コマンドは `python -m backend.main`）。
8. デプロイする。
9. アプリログと `/api/health` を確認する（200が返ること）。
10. `/api/metadata` で `data_mode` が想定通り（`demo` または `databricks`）であることを確認する。
11. **`/api/health` だけでなく、ブラウザでアプリを開いてUI（日本語ヘッダーと3カラムの空状態レイアウト）が実際に表示されることを確認する。**

## 12. アプリの使い方（Phase 1時点）

Phase 1では業務フローの土台のみが完成しています。画面を開くと以下が表示されます。

- ヘッダー：アプリ名、データモード（`合成データ（demo）` / `Databricks接続`）、最終更新時刻
- 左：「本日の優先顧客」の空状態（Phase 2でデータ接続予定）
- 中央：「顧客360」「休眠リスク」の空状態（Phase 2・Layer 2実装後に表示予定）
- 右：「次のアクション」の空状態（Layer 3実装後に表示予定）
- 下部：フィードバックループと本番化時の追加事項を表示する予定の領域

## 13. 実装上の仮定

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

## 14. 失敗時の対処

`frontend/dist/index.html` が見つからずproductionモードで起動が失敗した場合：

1. ログに出力された `frontend/dist/index.html が見つかりません。scripts/prepare_deploy.sh を実行してから再デプロイしてください。` を確認する。
2. ローカルで `bash scripts/prepare_deploy.sh` を実行し、型チェック・ビルド・テストがすべて成功することを確認する。
3. 生成された `frontend/dist` を含むフォルダーを、Databricksワークスペースの配置先へ再同期する。
4. Databricks Appsを再デプロイし、アプリログと `/api/health`・画面表示の両方を再確認する。

## 15. デモ前チェック（Phase 1時点で確認済みの項目）

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

## 16. 伝えること・伝えないこと

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
