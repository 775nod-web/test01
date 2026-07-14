import type { ReactNode } from "react";

export function KpiTile({
  label,
  value,
  variant = "default",
  footnote,
  tooltip,
}: {
  label: string;
  value: ReactNode;
  variant?: "default" | "risk" | "value";
  footnote?: string;
  tooltip?: string;
}) {
  const cls = variant === "risk" ? "kpi-tile kpi-tile--risk" : variant === "value" ? "kpi-tile kpi-tile--value" : "kpi-tile";
  return (
    <div className={cls}>
      <p className="kpi-tile__label" title={tooltip}>
        {label}
        {tooltip && (
          <span aria-hidden="true" style={{ color: "var(--text-secondary)" }}>
            ⓘ
          </span>
        )}
      </p>
      <p className="kpi-tile__value">{value}</p>
      {footnote && <p className="kpi-tile__footnote">{footnote}</p>}
    </div>
  );
}
