-- ============================================================
-- Step 2: 行フィルタ・列マスキング（workspace.gold スキーマ）
-- Free EditionでUnity Catalogのこの機能が使えるかを確認する。
-- ============================================================

-- 2-A. 店舗別アクセス制御の行フィルタ関数
CREATE OR REPLACE FUNCTION workspace.gold.store_access_filter(store_id STRING)
RETURN
    is_account_group_member('admins')
    OR EXISTS (
        SELECT 1
        FROM workspace.gold.user_store_mapping m
        WHERE m.user_email = current_user()
          AND m.store_id = store_id
    );

ALTER TABLE workspace.gold.gold_daily_store_sales
    SET ROW FILTER workspace.gold.store_access_filter ON (store_id);

ALTER TABLE workspace.gold.gold_store_ranking
    SET ROW FILTER workspace.gold.store_access_filter ON (store_id);

-- 2-B. PIIマスキング関数（customer_idのマスキング）
CREATE OR REPLACE FUNCTION workspace.gold.mask_customer_id(customer_id STRING)
RETURN
    CASE
        WHEN is_account_group_member('admins')
          OR is_account_group_member('data_quality_team')
        THEN customer_id
        ELSE 'MASKED'
    END;

ALTER TABLE workspace.gold.gold_unregistered_master_report
    ALTER COLUMN customer_id SET MASK workspace.gold.mask_customer_id;

-- ============================================================
-- 確認用クエリ
-- ============================================================
-- 行フィルタ確認: あなたは5店舗全てにマッピングされているので5店舗分表示されるはず
SELECT DISTINCT store_id FROM workspace.gold.gold_store_ranking ORDER BY store_id;

-- 列マスキング確認: admins/data_quality_teamグループに未所属なら customer_id が
-- 'MASKED' になるはず（自分がadminグループに入っている場合はそのまま表示される）
SELECT transaction_id, customer_id FROM workspace.gold.gold_unregistered_master_report LIMIT 5;
