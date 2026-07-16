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
- PythonからReactビルド成果物を配信する仕組み
- Databricks Apps向け `app.yaml`
- ホスト・ポート解決ロジックの単体テスト

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

Node.jsはReactのビルドにのみ使用します。Expressをバックエンドには使用しません。Streamlitも使用しません。

## 4. ディレクトリ構成（現状）

```text
.
├── CLAUDE.md
├── DEMO_SPEC.md
├── README.md
├── app.yaml
├── requirements.txt
├── .gitignore
├── backend/
│   ├── main.py              # FastAPIエントリーポイント（Reactビルドの配信を含む）
│   ├── config.py             # ホスト・ポート・データモード解決ロジック
│   ├── api/
│   │   └── routes.py         # /api/health, /api/metadata
│   └── tests/
│       ├── test_config.py
│       └── test_api.py
├── frontend/
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── index.html
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

`data/`、`scripts/`、`artifacts/` はPhase 2以降、合成データ生成・顧客360構築・モデル学習を実装する際に追加します。

## 5. 開発コマンド

### バックエンド（Python）

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windowsは .venv\Scripts\activate
pip install -r requirements.txt

# テスト実行
python -m pytest backend/tests -v

# 開発起動（既定ポート8000、環境変数未設定時）
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

# 型チェック＋本番ビルド（frontend/dist に出力）
npm run build
```

### 結合確認（Pythonがフロントエンドを配信）

```bash
# 1. フロントエンドをビルドする
cd frontend && npm run build && cd ..

# 2. Pythonサーバーを起動する（frontend/dist が存在すれば自動配信）
source .venv/bin/activate
python -m backend.main

# 3. 別ターミナルで確認する
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:8000/api/metadata
# ブラウザで http://127.0.0.1:8000/ を開き、日本語ヘッダーと空状態を確認する
```

## 6. ポート・ホスト解決

Pythonサーバーは次の優先順位で起動設定を解決します（`backend/config.py`）。

```text
Host: UVICORN_HOST → 0.0.0.0
Port: DATABRICKS_APP_PORT → UVICORN_PORT → PORT → 8000
```

- Databricks Appsでは、プラットフォームが提供する `DATABRICKS_APP_PORT` を優先して使用します。
- ローカル開発では `PORT` を設定でき、未設定の場合は8000を使用します。
- `app.yaml` 側では固定ポートを指定しません（起動コマンドのみ定義）。
- 優先順位はホスト・ポートとも `backend/tests/test_config.py` で単体テスト済みです。

## 7. データモードの解決

`backend/config.py` の `resolve_data_mode()` が、以下3つのDatabricks SQL接続用環境変数がすべて設定されている場合のみ `databricks` モードを返し、それ以外は `demo` モードにフォールバックします。

- `DATABRICKS_SERVER_HOSTNAME`
- `DATABRICKS_HTTP_PATH`
- `DATABRICKS_TOKEN`

Phase 1では実際のDatabricks SQL接続は行わず、モード判定のみを実装しています。実データ接続はPhase 2以降で追加します。

## 8. Databricks Appsへのデプロイ

正確な操作はワークスペースUIと利用可能な機能に合わせて確認してください。完成条件は、ローカル起動ではなくDatabricks Apps上で表示できることです。

基本手順：

1. フロントエンドをローカルまたはCI環境でビルドする（`cd frontend && npm install && npm run build`）。`frontend/dist` はGit管理対象外（`.gitignore`）のため、デプロイ元にはビルド成果物を含めるか、デプロイ直前にビルドを実行する。
2. リポジトリ（`backend/`、`frontend/dist`、`app.yaml`、`requirements.txt` を含む）をDatabricksワークスペースのフォルダーまたはGit連携先へ配置する。
3. Databricks Appsでカスタムアプリを作成する。
4. アプリのソースとして対象フォルダーまたはGitリポジトリを選ぶ。
5. Databricks SQLに接続する場合は、必要なDatabricksリソース（SQLウェアハウス等）をアプリへ追加し、`DATABRICKS_SERVER_HOSTNAME` / `DATABRICKS_HTTP_PATH` / `DATABRICKS_TOKEN` に相当する接続情報を設定する。未設定の場合はdemoモードで起動する。
6. Python起動処理が `DATABRICKS_APP_PORT` → `UVICORN_PORT` → `PORT` → `8000` の順でポートを解決し、ホストは `UVICORN_HOST` または `0.0.0.0` を使用することを確認する（`app.yaml` の起動コマンドは `python -m backend.main`）。
7. デプロイする。
8. アプリログと `/api/health` を確認する（200が返ること）。
9. `/api/metadata` で `data_mode` が想定通り（`demo` または `databricks`）であることを確認する。
10. ブラウザでアプリを開き、日本語ヘッダーと3カラムの空状態レイアウトが表示されることを確認する。

## 9. アプリの使い方（Phase 1時点）

Phase 1では業務フローの土台のみが完成しています。画面を開くと以下が表示されます。

- ヘッダー：アプリ名、データモード（`合成データ（demo）` / `Databricks接続`）、最終更新時刻
- 左：「本日の優先顧客」の空状態（Phase 2でデータ接続予定）
- 中央：「顧客360」「休眠リスク」の空状態（Phase 2・Layer 2実装後に表示予定）
- 右：「次のアクション」の空状態（Layer 3実装後に表示予定）
- 下部：フィードバックループと本番化時の追加事項を表示する予定の領域

## 10. 実装上の仮定

- 仮定：フロントエンドのビルド成果物（`frontend/dist`）はGit管理対象外とし、デプロイ前に `npm run build` を実行して生成する。
- 理由：ビルド成果物をリポジトリにコミットすると、ソースとの差分管理が煩雑になり、依存関係の更新時に不整合が生じやすいため。
- 本番で確認する事項：Databricksワークスペースへのデプロイ手順（Git連携またはフォルダー同期）において、`npm run build` を含むビルドステップを確実に実行できるか確認する。CI/CDパイプラインがない場合は、デプロイ前に手動でビルドしてから同期する運用にする。

- 仮定：Phase 1では `requirements.txt` にDatabricks SQL接続用ライブラリ（`databricks-sql-connector` 等）を含めていない。
- 理由：Phase 1の受け入れ条件は起動・ヘルスチェック・メタデータ・モード判定のみであり、実データ接続はPhase 2以降のスコープのため。
- 本番で確認する事項：Phase 2でDatabricks SQLへの実接続を実装する際に、必要なライブラリと接続処理を追加する。

- 仮定：ルートに `package.json` を置かず、`frontend/package.json` のみでNode依存関係を管理する。
- 理由：Node.jsはフロントエンドのビルド専用であり、ルートにNodeパッケージを持つ必然性がないため（本番プロセスはPythonのみ）。
- 本番で確認する事項：Databricksへのデプロイ手順で、ビルドを `frontend/` 配下で実行する運用が周知されているか確認する。

## 11. デモ前チェック（Phase 1時点で確認済みの項目）

- [x] `python -m pytest backend/tests` が全件成功する
- [x] `npm run typecheck` がエラーなく完了する
- [x] `npm run build` が成功し `frontend/dist` が生成される
- [x] ローカルで `python -m backend.main` を起動し、`/api/health` が200を返す
- [x] `/api/metadata` がDatabricks接続情報の有無に応じて `demo` / `databricks` を正しく返す
- [x] ビルド後、Pythonサーバーが `frontend/dist/index.html` を配信し、日本語タイトルが表示される
- [ ] Databricks Apps上での実デプロイ確認（Phase 1では未実施、ワークスペースアクセスが必要）

## 12. 伝えること・伝えないこと

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
