import type { ReactNode } from "react";
import { ink, surface } from "../theme/colors";

interface KpiCardProps {
  label: string;
  value: string;
  accent: string;
  sub?: ReactNode;
}

export function KpiCard({ label, value, accent, sub }: KpiCardProps) {
  return (
    <div
      style={{
        background: surface.card,
        borderRadius: 14,
        padding: "18px 20px",
        border: `1px solid ${surface.border}`,
        borderTop: `4px solid ${accent}`,
        minWidth: 180,
        flex: "1 1 180px",
      }}
    >
      <div style={{ fontSize: 12, color: ink.muted, marginBottom: 6 }}>{label}</div>
      <div style={{ fontSize: 26, fontWeight: 700, color: ink.primary }}>{value}</div>
      {sub && <div style={{ fontSize: 12, color: ink.secondary, marginTop: 4 }}>{sub}</div>}
    </div>
  );
}
