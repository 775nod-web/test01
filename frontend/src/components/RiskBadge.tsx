import type { RiskBand } from "../types";

const RISK_ICON: Record<RiskBand, string> = {
  high: "🔴",
  medium: "🟡",
  low: "🟢",
};

const RISK_CLASS: Record<RiskBand, string> = {
  high: "badge badge--risk-high",
  medium: "badge badge--risk-medium",
  low: "badge badge--risk-low",
};

export function RiskBadge({ band, label }: { band: RiskBand; label: string }) {
  return (
    <span className={RISK_CLASS[band]}>
      <span aria-hidden="true">{RISK_ICON[band]}</span>
      {label}リスク
    </span>
  );
}
