interface KpiCardProps {
  label: string;
  value: string;
  note?: string;
  accentColor?: string;
}

export function KpiCard({ label, value, note, accentColor }: KpiCardProps) {
  return (
    <div className="kpi-card" style={accentColor ? { borderLeftColor: accentColor } : undefined}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
      {note && <div className="kpi-note">{note}</div>}
    </div>
  );
}
