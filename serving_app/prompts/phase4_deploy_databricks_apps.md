# Phase 4: Databricks Appsへのデプロイ

## 前提

このフェーズは、Databricks CLIが認証済みの環境（ユーザー自身のワークステーション
やDatabricks CLIアクセスのあるセッション）から実行する。認証情報の無い
サンドボックス環境からは実行できない。

## 絶対に守ること

**Databricks Appsの数が上限に達していてデプロイできない場合でも、
他ユーザーが作成した最も古いアプリ（またはどのアプリであっても）を
自動的に削除しない。** 対応は以下のいずれかとする。

1. `databricks apps list` で既存アプリの一覧と所有者を確認し、
   ワークスペース管理者・該当アプリの所有者に相談する。
2. 自分自身が作成した不要なテスト用アプリがあれば、それを削除する
   （他人のアプリではないことを`databricks apps get <name>`等で確認してから）。
3. どちらも難しい場合は、デプロイを保留してユーザーに状況を報告する。

## 手順

1. フロントエンドをビルドする。
   ```bash
   cd serving_app/frontend
   npm install
   npm run build
   ```
2. Databricks Apps用のアプリをワークスペースに作成する（未作成の場合）。
   ```bash
   databricks apps create <app-name>
   ```
3. コードをデプロイする。
   ```bash
   cd ..
   databricks apps deploy <app-name> --source-code-path .
   ```
4. Databricks Apps UIの「Resources」設定で、SQL Warehouse
   （`50153ad923fecd73`、Serverless Starter Warehouse）へのアクセス権を
   このアプリのサービスプリンシパルに付与する。
5. Gold layerの表がUnity Catalogの特定カタログ配下にある場合は、
   `app.yaml` の `GOLD_TABLE_PREFIX` を `<catalog>.gold` に書き換えて
   再デプロイする。
6. デプロイ後、アプリのURLで以下を確認する。
   - `/api/health` が200を返すこと
   - ダッシュボードの4パネル（店舗ランキング／カテゴリ別売上／日別店舗別売上／
     マスター未登録レポート）にGold layerの実データが表示されること
   - ライト/ダーク切り替えが正しく機能すること

## トラブルシューティング

- `/api/*` が500を返す場合: Warehouseへのアクセス権限、
  `DATABRICKS_WAREHOUSE_ID` の値、Gold表のカタログ/スキーマ修飾を確認する。
- フロントエンドが真っ白になる場合: `npm run build` が
  `frontend/dist` を生成できているか、`backend/main.py` が
  それをマウントできているかを確認する。
