-- ============================================================
-- Step 1: 前提テーブルの作成（workspace.gold スキーマ）
-- Databricks SQLエディタで、Warehouse = Serverless Starter Warehouse を
-- 選択した状態で、上から順に実行してください。
-- ============================================================

-- 1-A. 店舗別アクセス制御の基礎となるユーザー×店舗マッピングテーブル
CREATE TABLE IF NOT EXISTS workspace.gold.user_store_mapping (
    user_email STRING NOT NULL,
    store_id   STRING NOT NULL
)
COMMENT '店舗別アクセス制御: どのユーザーがどの店舗のデータを閲覧できるかのマッピング';

-- 1-B. デモ用: 今このSQLを実行しているユーザーを、実在する5店舗すべての
--      担当者として登録する（後で複数ユーザー・複数店舗に分けたくなったら
--      個別にINSERTし直せばよい）
INSERT INTO workspace.gold.user_store_mapping
SELECT current_user(), store_id
FROM workspace.silver.silver_store_master;

-- 1-C. 売上急減しきい値アラートの出力先テーブル
CREATE TABLE IF NOT EXISTS workspace.gold.gold_sales_alerts (
    alert_date        DATE   NOT NULL,
    store_id          STRING NOT NULL,
    store_name        STRING NOT NULL,
    sales_change_pct  DOUBLE NOT NULL,
    threshold_pct     DOUBLE NOT NULL,
    message           STRING NOT NULL
)
COMMENT '前日比・前週比の売上急減アラート（しきい値超過分のみ格納）';

-- 1-D. 監査ログのフォールバックテーブル（system.access.auditが使えない場合用）
CREATE TABLE IF NOT EXISTS workspace.gold.app_access_log (
    event_time       TIMESTAMP NOT NULL,
    user_email       STRING    NOT NULL,
    endpoint         STRING    NOT NULL,
    store_id_filter  STRING
)
COMMENT 'アプリ内簡易監査ログ: 誰がいつどのAPI/店舗データにアクセスしたか';

-- ============================================================
-- 確認用クエリ（実行後に流して、作成・投入結果を確認してください）
-- ============================================================
SELECT * FROM workspace.gold.user_store_mapping;
