-- Phase 3-C fallback audit log, written to by app/backend/audit.py on every
-- /api/* request and read by GET /api/audit-log.
--
-- NOT RUN — same caveat as 001_user_store_mapping.sql. This is the fallback
-- for system.access.audit: whether that system table is queryable on this
-- workspace/edition was never checked from this coding session (no network
-- access). If it turns out to be available, prefer it going forward — it
-- captures activity this app-level log cannot see (direct SQL/notebook
-- access to the same Gold/Silver tables, other apps, etc).

CREATE TABLE IF NOT EXISTS workspace.silver.silver_app_audit_log (
  logged_at TIMESTAMP NOT NULL,
  user_email STRING NOT NULL,
  endpoint STRING NOT NULL,
  store_id_filter STRING,
  status_code INT NOT NULL
)
USING DELTA
COMMENT 'Phase 3-C fallback audit log for the retail_sales_demo serving layer API.';
