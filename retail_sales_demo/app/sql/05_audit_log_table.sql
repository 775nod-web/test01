-- 監査ログのフォールバック実装（system.access.audit がFree Editionで
-- 利用できない場合に、アプリ自身がアクセスを記録するための簡易テーブル）。

CREATE TABLE IF NOT EXISTS ${catalog}.${schema}.app_access_log (
    event_time       TIMESTAMP NOT NULL,
    user_email       STRING    NOT NULL,
    endpoint         STRING    NOT NULL,
    store_id_filter  STRING
)
COMMENT 'アプリ内簡易監査ログ: 誰がいつどのAPI/店舗データにアクセスしたか';
