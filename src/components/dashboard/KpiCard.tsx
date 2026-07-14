import type { KpiValue } from "../../types";
import { formatByUnit, formatDelta } from "../../utils/format";
import InfoTooltip from "../common/InfoTooltip";

interface KpiCardProps {
  kpi: KpiValue;
  size?: "large" | "small";
}

function deltaDirectionClass(delta: number, key: string): string {
  if (delta === 0) return "kpi-delta-flat";
  // 誤検知率・平均検知時間・平均調査時間・調査待ち件数は「減少」が改善
  const lowerIsBetter = [
    "false_positive_rate",
    "avg_detection_time_minutes",
    "avg_investigation_time_minutes",
    "pending_investigation_count",
    "confirmed_fraud_rate",
  ].includes(key);
  const improved = lowerIsBetter ? delta < 0 : delta > 0;
  return improved ? "kpi-delta-good" : "kpi-delta-bad";
}

function KpiCard({ kpi, size = "small" }: KpiCardProps) {
  return (
    <div className={`kpi-card kpi-card-${size}`}>
      <div className="kpi-card-header">
        <span className="kpi-card-label">{kpi.label}</span>
        <InfoTooltip label={kpi.label} description={kpi.description} />
      </div>
      <div className="kpi-card-value">{formatByUnit(kpi.value, kpi.unit)}</div>
      <div className={`kpi-card-delta ${deltaDirectionClass(kpi.delta, kpi.key)}`}>
        前期間比 {formatDelta(kpi.delta, kpi.unit)}
      </div>
    </div>
  );
}

export default KpiCard;
