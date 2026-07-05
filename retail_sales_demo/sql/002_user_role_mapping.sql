-- Phase 3-B/3-C fallback: role grants, read by
-- app/backend/access_control.py (build_user_role_mapping_query).
--
-- NOT RUN — same caveat as 001_user_store_mapping.sql.
--
-- Roles used by the app:
--   PII_VIEWER   - sees unmasked customer_id in /api/quarantine-report
--   AUDIT_VIEWER - can call /api/audit-log
-- A user with no rows here gets neither. Admins (store mapping 'ALL' in
-- 001_user_store_mapping.sql) also implicitly get both, regardless of rows
-- here — see AccessContext.can_view_pii / can_view_audit_log.

CREATE TABLE IF NOT EXISTS workspace.silver.silver_user_role_mapping (
  user_email STRING NOT NULL,
  role STRING NOT NULL COMMENT 'PII_VIEWER, AUDIT_VIEWER, ...'
)
USING DELTA
COMMENT 'Phase 3 demo role grants. Replace the seed rows below with real users before relying on this for anything beyond a demo.';

INSERT INTO workspace.silver.silver_user_role_mapping (user_email, role) VALUES
  ('dq-demo@example.com', 'PII_VIEWER'),
  ('dq-demo@example.com', 'AUDIT_VIEWER');
