-- Phase 3-A fallback: user -> store access mapping, read by
-- app/backend/access_control.py (build_user_store_mapping_query).
--
-- NOT RUN — this coding session has no access to the Databricks workspace.
-- Run this once against the live workspace before Phase 3's access control
-- can do anything beyond "deny everyone" (no rows = no access, per
-- access_control.resolve_effective_store_ids).
--
-- The special store_id value 'ALL' grants access to every store (used here
-- for the HQ/admin demo identity).

CREATE TABLE IF NOT EXISTS workspace.silver.silver_user_store_mapping (
  user_email STRING NOT NULL COMMENT 'Matches the Databricks Apps X-Forwarded-Email header value',
  store_id STRING NOT NULL COMMENT 'gold_daily_store_sales.store_id, or the literal "ALL" for every store'
)
USING DELTA
COMMENT 'Phase 3 demo user-to-store access mapping. Replace the seed rows below with real users before relying on this for anything beyond a demo.';

-- Demo seed data — replace with real users/emails before use.
INSERT INTO workspace.silver.silver_user_store_mapping (user_email, store_id) VALUES
  ('hq-demo@example.com', 'ALL'),
  ('store1-demo@example.com', 'S001'),
  ('store2-demo@example.com', 'S002'),
  ('dq-demo@example.com', 'ALL');
