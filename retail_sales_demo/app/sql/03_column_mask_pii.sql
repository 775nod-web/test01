-- PIIマスキング: gold_unregistered_master_report.customer_id を
-- data_quality_team / admins グループ以外にはマスクする。

CREATE OR REPLACE FUNCTION ${catalog}.${schema}.mask_customer_id(customer_id STRING)
RETURN
    CASE
        WHEN is_account_group_member('admins')
          OR is_account_group_member('data_quality_team')
        THEN customer_id
        ELSE 'MASKED'
    END;

ALTER TABLE ${catalog}.${schema}.gold_unregistered_master_report
    ALTER COLUMN customer_id SET MASK ${catalog}.${schema}.mask_customer_id;
