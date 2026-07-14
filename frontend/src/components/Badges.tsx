import { HUMAN_REVIEW_REQUIRED_LABEL, t } from "../i18n/ja";
import type { RiskSegment, ValueSegment } from "../types";

export function RiskBadge({ segment }: { segment: RiskSegment }) {
  const cls =
    segment === "High" ? "badge--risk-high" : segment === "Medium" ? "badge--risk-medium" : "badge--risk-low";
  return <span className={`badge ${cls}`}>{t.riskSegment(segment)}</span>;
}

export function ValueBadge({ segment }: { segment: ValueSegment }) {
  const cls =
    segment === "High" ? "badge--value-high" : segment === "Medium" ? "badge--value-medium" : "badge--value-low";
  return <span className={`badge ${cls}`}>{t.valueSegment(segment)}</span>;
}

export function HumanReviewBadge({ required }: { required: number | boolean }) {
  if (!required) return null;
  return (
    <span className="badge badge--review" title="担当者が確認・承認するまで、顧客への連絡は行われません。">
      {HUMAN_REVIEW_REQUIRED_LABEL}
    </span>
  );
}
