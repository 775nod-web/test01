-- 店舗別アクセス制御の基礎となるユーザー×店舗マッピングテーブル。
-- UC行フィルタ方式・API側フィルタ方式のどちらを採用する場合でも、この表を参照する。
-- ${catalog} / ${schema} は実環境の値に置き換えて実行すること。

CREATE TABLE IF NOT EXISTS ${catalog}.${schema}.user_store_mapping (
    user_email STRING NOT NULL,
    store_id   STRING NOT NULL
)
COMMENT '店舗別アクセス制御: どのユーザーがどの店舗のデータを閲覧できるかのマッピング';

-- デモ用サンプルデータ例（実データに合わせて置き換える）
-- INSERT INTO ${catalog}.${schema}.user_store_mapping VALUES
--   ('store001-manager@example.com', 'STORE_001'),
--   ('hq-sales@example.com', 'STORE_001'),
--   ('hq-sales@example.com', 'STORE_002');
