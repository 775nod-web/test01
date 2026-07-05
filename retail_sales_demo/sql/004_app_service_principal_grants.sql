-- Phase 4: grants the Databricks Apps service principal needs to run the
-- Serving layer backend. Replace `<APP_SERVICE_PRINCIPAL>` with the actual
-- service principal / application ID Databricks Apps assigns this app on
-- creation (visible in the app's "Authorization" tab once created).
--
-- NOT RUN — this coding session has no access to the Databricks workspace,
-- so the exact grant statements below have not been executed or confirmed
-- against the real catalog/schema. Adjust catalog/schema names if Phase 0's
-- assumption (catalog "workspace", schemas "gold"/"silver") doesn't match.

GRANT USE CATALOG ON CATALOG workspace TO `<APP_SERVICE_PRINCIPAL>`;
GRANT USE SCHEMA ON SCHEMA workspace.gold TO `<APP_SERVICE_PRINCIPAL>`;
GRANT USE SCHEMA ON SCHEMA workspace.silver TO `<APP_SERVICE_PRINCIPAL>`;

-- Read access: the four Gold tables the API serves, plus the two
-- Phase 3 batch-output tables it reads (created by jobs/alert_batch.py and
-- jobs/requeue_batch.py on first run).
GRANT SELECT ON TABLE workspace.gold.gold_daily_store_sales TO `<APP_SERVICE_PRINCIPAL>`;
GRANT SELECT ON TABLE workspace.gold.gold_category_sales TO `<APP_SERVICE_PRINCIPAL>`;
GRANT SELECT ON TABLE workspace.gold.gold_store_ranking TO `<APP_SERVICE_PRINCIPAL>`;
GRANT SELECT ON TABLE workspace.gold.gold_unregistered_master_report TO `<APP_SERVICE_PRINCIPAL>`;
GRANT SELECT ON TABLE workspace.gold.gold_store_sales_alerts TO `<APP_SERVICE_PRINCIPAL>`;
GRANT SELECT ON TABLE workspace.gold.gold_requeue_batch_runs TO `<APP_SERVICE_PRINCIPAL>`;

-- Read+write: the Phase 3 governance tables the API reads (mappings) and
-- writes (audit log).
GRANT SELECT ON TABLE workspace.silver.silver_user_store_mapping TO `<APP_SERVICE_PRINCIPAL>`;
GRANT SELECT ON TABLE workspace.silver.silver_user_role_mapping TO `<APP_SERVICE_PRINCIPAL>`;
GRANT SELECT, MODIFY ON TABLE workspace.silver.silver_app_audit_log TO `<APP_SERVICE_PRINCIPAL>`;

-- Warehouse: CAN_USE on the Serverless Starter Warehouse (id 50153ad923fecd73).
-- This is typically granted via the Databricks Apps UI when attaching the
-- warehouse as an app "resource" rather than via SQL — if doing it manually,
-- use the Warehouse's Permissions tab or:
--   databricks warehouses set-permissions 50153ad923fecd73 \
--     --json '{"access_control_list": [{"service_principal_name": "<APP_SERVICE_PRINCIPAL>", "permission_level": "CAN_USE"}]}'

-- Jobs: triggering jobs/requeue_batch.py (POST /api/requeue-trigger) needs
-- CAN_MANAGE_RUN (or CAN_MANAGE) on that job — this is a Jobs permission,
-- not a SQL grant, granted once the job exists:
--   databricks jobs update-permissions <REQUEUE_JOB_ID> \
--     --json '{"access_control_list": [{"service_principal_name": "<APP_SERVICE_PRINCIPAL>", "permission_level": "CAN_MANAGE_RUN"}]}'
