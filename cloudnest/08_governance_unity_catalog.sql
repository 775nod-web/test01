-- ======================================================
-- CloudNest ガバナンス設計（Unity Catalog）
-- ======================================================
-- 課題7「個人情報・契約情報を含むためアクセス制御・監査・リネージが必要」への対応。
--
-- ★注意：このスクリプトは Unity Catalog が有効なワークスペースでの実行を前提とする。
--   本プロトタイプのライブデモ環境（Databricks Free Edition / Hive メタストア）では
--   Unity Catalog のカタログ・グループ・行/列レベルセキュリティ機能が使えないため、
--   このファイルは「本番PoC・本番運用でこう設計する」という提案として提示するもの。
--   （01〜07のノートブックは database 名（bronze/silver/gold）を
--     Unity Catalog では `<catalog>.<schema>` に読み替えるだけで概ねそのまま動く）


-- ==================================================
-- 1. カタログ／スキーマ構成
-- ==================================================
-- 環境ごとにカタログを分離（開発／本番）し、スキーマでメダリオン層を分離する
CREATE CATALOG IF NOT EXISTS cloudnest_prod;
CREATE SCHEMA IF NOT EXISTS cloudnest_prod.bronze;
CREATE SCHEMA IF NOT EXISTS cloudnest_prod.silver;
CREATE SCHEMA IF NOT EXISTS cloudnest_prod.gold;

-- データ分類タグ付け（個人情報・財務情報の棚卸しと監査証跡のために付与）
ALTER TABLE cloudnest_prod.silver.cloudnest_silver_customer_master
  SET TAGS ('data_classification' = 'confidential', 'contains_pii' = 'false');
ALTER TABLE cloudnest_prod.silver.cloudnest_silver_contracts
  SET TAGS ('data_classification' = 'confidential', 'contains_financial_data' = 'true');
ALTER TABLE cloudnest_prod.silver.cloudnest_silver_billing
  SET TAGS ('data_classification' = 'restricted', 'contains_financial_data' = 'true');
ALTER TABLE cloudnest_prod.silver.cloudnest_silver_support_tickets
  SET TAGS ('data_classification' = 'confidential', 'contains_pii' = 'true');  -- 問い合わせ本文に個人名等が含まれ得る


-- ==================================================
-- 2. ロールベースアクセス制御（Unity Catalog グループに対するGRANT）
--    前提グループ：cs_team / data_science_team / executives / data_engineers
-- ==================================================

-- データエンジニアリングチーム：全層に対するフル権限（パイプライン運用）
GRANT USE CATALOG, USE SCHEMA ON CATALOG cloudnest_prod TO `data_engineers`;
GRANT ALL PRIVILEGES ON SCHEMA cloudnest_prod.bronze TO `data_engineers`;
GRANT ALL PRIVILEGES ON SCHEMA cloudnest_prod.silver TO `data_engineers`;
GRANT ALL PRIVILEGES ON SCHEMA cloudnest_prod.gold TO `data_engineers`;

-- Customer Success チーム：Gold層のみ参照可（Bronze/Silverの生データには触れさせない）
GRANT USE CATALOG ON CATALOG cloudnest_prod TO `cs_team`;
GRANT USE SCHEMA ON SCHEMA cloudnest_prod.gold TO `cs_team`;
GRANT SELECT ON VIEW cloudnest_prod.gold.v_customer_360_cs TO `cs_team`;  -- 行レベルフィルタ付きビュー（下記3参照）

-- 経営層：全社集計ビューのみ参照可（個社の詳細は見せない設計も可能。ここでは集計＋トップ勘定まで許可）
GRANT USE CATALOG ON CATALOG cloudnest_prod TO `executives`;
GRANT USE SCHEMA ON SCHEMA cloudnest_prod.gold TO `executives`;
GRANT SELECT ON TABLE cloudnest_prod.gold.cloudnest_gold_health_score_history TO `executives`;
GRANT SELECT ON VIEW cloudnest_prod.gold.v_customer_360_exec TO `executives`;  -- 列マスキング付きビュー（下記4参照）

-- データサイエンスチーム：学習用にGold層への読み取りアクセス（PIIカラムは列マスキングビュー経由）
GRANT USE CATALOG ON CATALOG cloudnest_prod TO `data_science_team`;
GRANT USE SCHEMA ON SCHEMA cloudnest_prod.gold TO `data_science_team`;
GRANT SELECT ON TABLE cloudnest_prod.gold.cloudnest_gold_customer_360 TO `data_science_team`;
GRANT SELECT ON TABLE cloudnest_prod.gold.cloudnest_gold_health_score_latest TO `data_science_team`;


-- ==================================================
-- 3. 行レベルセキュリティ（Row-Level Security）
--    CS担当者は自分が担当する顧客（csm_owner = 自分）のみ閲覧可能にする
-- ==================================================

CREATE OR REPLACE FUNCTION cloudnest_prod.gold.csm_row_filter(csm_owner STRING)
RETURN
  is_account_group_member('executives')          -- 経営層・管理者は全件閲覧可
  OR is_account_group_member('data_engineers')
  OR csm_owner = current_user();                  -- CS担当者は自分の担当顧客のみ

ALTER TABLE cloudnest_prod.gold.cloudnest_gold_customer_360
  SET ROW FILTER cloudnest_prod.gold.csm_row_filter ON (csm_owner);


-- ==================================================
-- 4. 列レベルマスキング（Column Masking）
--    財務情報（正確なARR金額）は経営層・財務・担当CSMのみ閲覧可能とし、
--    それ以外のロールにはレンジ表示（例：¥10M〜¥50M）でマスクする
-- ==================================================

CREATE OR REPLACE FUNCTION cloudnest_prod.gold.mask_arr(arr_usd DOUBLE)
RETURN
  CASE
    WHEN is_account_group_member('executives') OR is_account_group_member('finance_team') THEN arr_usd
    WHEN arr_usd < 10000 THEN 'under $10K'
    WHEN arr_usd < 50000 THEN '$10K-$50K'
    WHEN arr_usd < 150000 THEN '$50K-$150K'
    ELSE '$150K+'
  END;

ALTER TABLE cloudnest_prod.gold.cloudnest_gold_customer_360
  ALTER COLUMN arr_usd SET MASK cloudnest_prod.gold.mask_arr;

-- CS/経営層向けの参照用ビュー（上記の行フィルタ・列マスキングは基底テーブルに設定済みのため、
-- ビューは可読性目的で必要な列のみに絞る）
CREATE OR REPLACE VIEW cloudnest_prod.gold.v_customer_360_cs AS
SELECT customer_id, company_name, industry, csm_owner, plan, arr_usd, days_to_renewal,
       usage_trend_pct, seat_utilization_rate, tickets_last_90d, avg_csat_last_90d,
       overdue_invoices_last_180d
FROM cloudnest_prod.gold.cloudnest_gold_customer_360;

CREATE OR REPLACE VIEW cloudnest_prod.gold.v_customer_360_exec AS
SELECT industry, region, employee_band, plan, csm_owner,
       COUNT(*) AS customer_count, SUM(arr_usd) AS total_arr
FROM cloudnest_prod.gold.cloudnest_gold_customer_360
GROUP BY industry, region, employee_band, plan, csm_owner;


-- ==================================================
-- 5. 監査（Audit）
--    Unity Catalog は全テーブルへのアクセス（SELECT/GRANT/権限変更等）を
--    system.access.audit テーブルに自動記録する。誰が・いつ・どのテーブルに
--    アクセスしたかを追跡できる（追加設定不要）。
-- ==================================================

-- 例：直近30日の Customer 360 テーブルへのアクセス履歴を確認
-- SELECT event_time, user_identity.email, action_name, request_params
-- FROM system.access.audit
-- WHERE service_name = 'unityCatalog'
--   AND request_params.table_full_name = 'cloudnest_prod.gold.cloudnest_gold_customer_360'
--   AND event_time >= current_date() - INTERVAL 30 DAYS
-- ORDER BY event_time DESC;


-- ==================================================
-- 6. リネージ（Lineage）
--    Unity Catalog は Bronze→Silver→Gold のテーブル／カラム単位のリネージを
--    コード変更なしに自動収集する（Catalog Explorer上でグラフ表示可能）。
--    system.access テーブル経由でプログラムからも取得可能。
-- ==================================================

-- 例：health_score が Bronze のどのソーステーブルに由来するかをカラム単位で追跡
-- SELECT source_table_full_name, source_column_name, target_column_name
-- FROM system.access.column_lineage
-- WHERE target_table_full_name = 'cloudnest_prod.gold.cloudnest_gold_health_score_latest';


-- ==================================================
-- 7. 本番運用での補足事項（提案書・Q&Aで言及）
-- ==================================================
-- - Delta Lake の DESCRIBE HISTORY によるバージョン管理・タイムトラベルで変更履歴を保持
-- - Lakehouse Monitoring でヘルススコア分布のドリフト・データ品質を継続監視
-- - サポートチケット本文の個人情報は、Silver層でのマスキング／匿名化処理を追加検討
--   （例：正規表現による氏名・メールアドレスの自動マスキング、またはDLPスキャン）
