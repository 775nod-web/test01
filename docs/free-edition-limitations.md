# Databricks Free Edition limitations

> Placeholder created in Phase 1; expanded as each phase surfaces concrete
> constraints, and finalized in Phase 8.

## Confirmed constraints (assumed per CLAUDE.md)

- Serverless-only compute; one 2X-Small SQL warehouse; fair-use quotas; no SLA.
- Maximum of three Databricks Apps per account; Apps auto-stop after up to
  24 hours of inactivity and must be manually restarted.
- No SSO, SCIM, private networking, online tables, or production-grade
  enterprise controls.
- No real bank connectivity or real customer data anywhere in this project.
- Outbound internet access may be restricted; this project does not depend
  on external network calls at runtime.

## Observed during this build

- This coding session had no network path to the target Databricks
  workspace (outbound HTTPS blocked by session egress policy), so workspace
  capabilities (catalog availability, serverless warehouse state, Databricks
  Apps quota) could not be verified directly and must be confirmed by the
  user before Phase 2.

## Not implemented in this demo (by design)

- No real-time/streaming inference.
- No fully automated Next Best Action — all recommendations require human
  review.
- No production-grade model serving.
- No automatic handoff to external marketing platforms.
