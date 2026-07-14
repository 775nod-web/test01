import type { RiskSegment, ValueSegment } from "../types";

export function RiskBadge({ segment }: { segment: RiskSegment }) {
  const cls =
    segment === "High" ? "badge--risk-high" : segment === "Medium" ? "badge--risk-medium" : "badge--risk-low";
  return <span className={`badge ${cls}`}>{segment} risk</span>;
}

export function ValueBadge({ segment }: { segment: ValueSegment }) {
  const cls =
    segment === "High" ? "badge--value-high" : segment === "Medium" ? "badge--value-medium" : "badge--value-low";
  return <span className={`badge ${cls}`}>{segment} value</span>;
}

export function HumanReviewBadge({ required }: { required: number | boolean }) {
  if (!required) return null;
  return (
    <span className="badge badge--review" title="A person must review and approve this before any customer contact.">
      Human review required
    </span>
  );
}
