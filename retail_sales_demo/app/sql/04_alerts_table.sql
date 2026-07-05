-- 売上急減しきい値アラート（追加機能・優先度高）の出力先テーブル。
-- jobs/sales_drop_alert_job.py が日次でこのテーブルを更新する。

CREATE TABLE IF NOT EXISTS ${catalog}.${schema}.gold_sales_alerts (
    alert_date        DATE   NOT NULL,
    store_id          STRING NOT NULL,
    store_name        STRING NOT NULL,
    sales_change_pct  DOUBLE NOT NULL,
    threshold_pct     DOUBLE NOT NULL,
    message           STRING NOT NULL
)
COMMENT '前日比・前週比の売上急減アラート（しきい値超過分のみ格納）';
