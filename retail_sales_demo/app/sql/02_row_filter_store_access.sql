-- 【優先案】Unity Catalog 行フィルタによる店舗別アクセス制御。
-- Free Editionでこの機能が利用可能かはPhase 3で実際に検証すること。
-- 利用できない場合は backend/main.py の ROW_FILTER_ENABLED_BY_UC=false のまま、
-- API側フィルタ（queries.get_allowed_stores）にフォールバックする。

CREATE OR REPLACE FUNCTION ${catalog}.${schema}.store_access_filter(store_id STRING)
RETURN
    is_account_group_member('admins')
    OR EXISTS (
        SELECT 1
        FROM ${catalog}.${schema}.user_store_mapping m
        WHERE m.user_email = current_user()
          AND m.store_id = store_id
    );

ALTER TABLE ${catalog}.${schema}.gold_daily_store_sales
    SET ROW FILTER ${catalog}.${schema}.store_access_filter ON (store_id);

ALTER TABLE ${catalog}.${schema}.gold_store_ranking
    SET ROW FILTER ${catalog}.${schema}.store_access_filter ON (store_id);

-- 有効化できた場合は、Databricks Apps の環境変数 ROW_FILTER_ENABLED_BY_UC を "true" に変更し、
-- backend側の二重フィルタを無効化すること。
