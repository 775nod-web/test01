# Phase 1: バックエンド（FastAPI）の構築

## 目的

Gold layerの4表を読み取り専用で配信するREST APIを、Databricks Apps上で
動く単一プロセスのFastAPIアプリとして実装する。

## やること

1. `serving_app/requirements.txt` に `fastapi` / `uvicorn[standard]` /
   `databricks-sql-connector` / `databricks-sdk` を追加する。
2. `serving_app/backend/db.py`:
   - `databricks.sdk.core.Config` と `databricks.sql.connect` を使い、
     Databricks Apps実行環境で自動的に注入される認証情報から
     Warehouseへ接続するヘルパーを実装する。
   - `Config()` の生成は**遅延初期化**にする（モジュールimport時に
     即座に呼ばない）。Databricks認証情報が無い環境でimportするだけで
     アプリ全体がクラッシュしないようにするため。
   - Warehouse IDは環境変数 `DATABRICKS_WAREHOUSE_ID`（デフォルト
     `50153ad923fecd73`）から読む。
   - Gold表の参照は `GOLD_TABLE_PREFIX`（デフォルト `gold`）を使って
     組み立てる関数を用意し、クエリ側にスキーマ名をハードコードしない。
3. `serving_app/backend/queries.py`:
   - 4表それぞれに対応する読み取り専用のSELECT関数を1つずつ実装する。
   - `date` / `Decimal` 型をJSONで表現できる型（str / float）に変換する
     ヘルパーを必ず通す（そのまま返すとJSONシリアライズに失敗する）。
4. `serving_app/backend/main.py`:
   - `/api/health` と、4表に対応する4つのGETエンドポイントを実装する。
   - 各エンドポイントは例外を捕捉し、500エラーとして返す（プロセスを
     クラッシュさせない）。
   - `frontend/dist` が存在する場合のみ静的ファイル配信を有効にする
     （ビルド前のバックエンド単体起動でもエラーにならないように）。

## 完了確認

- `python3 -m py_compile backend/*.py` が通ること。
- Databricks認証情報が無い状態で `uvicorn backend.main:app` を起動し、
  `/api/health` が200を返し、他の `/api/*` は500（クラッシュではない）に
  なることを確認する。
