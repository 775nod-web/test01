/**
 * Demo-only stand-ins for real logged-in identities, sent as the
 * X-Forwarded-Email header (see ApiFilters.asUser). These must match the
 * seed rows in retail_sales_demo/sql/001_user_store_mapping.sql and
 * 002_user_role_mapping.sql for the access-control/PII-masking demo to show
 * anything meaningful. Once Phase 3's SSO-forwarded identity is confirmed
 * working, this selector (and the whole X-Forwarded-Email demo affordance)
 * should be removed — real deployments never let the client pick who it is.
 */
export interface DemoIdentity {
  email: string;
  label: string;
}

export const DEMO_IDENTITIES: DemoIdentity[] = [
  { email: 'hq-demo@example.com', label: '本社管理者（全店舗・PII閲覧可）' },
  { email: 'dq-demo@example.com', label: 'データ品質チーム（全店舗・PII閲覧可・監査ログ閲覧可）' },
  { email: 'store1-demo@example.com', label: '店長（店舗S001のみ）' },
  { email: 'store2-demo@example.com', label: '店長（店舗S002のみ）' },
];
