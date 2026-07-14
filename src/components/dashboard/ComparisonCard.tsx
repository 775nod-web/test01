import type { Scenario, ScenarioComparison } from "../../types";
import { formatJpy, formatPercent } from "../../utils/format";

interface ComparisonCardProps {
  comparison: ScenarioComparison;
  activeScenario: Scenario;
}

interface Row {
  label: string;
  format: (m: ScenarioComparison["rules"]) => string;
}

const ROWS: Row[] = [
  { label: "不正捕捉率", format: (m) => formatPercent(m.fraud_capture_rate) },
  { label: "正常承認率", format: (m) => formatPercent(m.normal_approval_rate) },
  { label: "誤検知率", format: (m) => formatPercent(m.false_positive_rate) },
  { label: "推定防止損失", format: (m) => formatJpy(m.prevented_loss_amount) },
  { label: "平均調査時間", format: (m) => `${m.avg_investigation_time_minutes.toFixed(1)}分` },
];

function ComparisonCard({ comparison, activeScenario }: ComparisonCardProps) {
  return (
    <section className="card comparison-card" aria-labelledby="comparison-heading">
      <h2 id="comparison-heading">既存ルールのみ vs ルール＋AI</h2>
      <div className="table-scroll">
        <table className="comparison-table">
          <thead>
            <tr>
              <th scope="col">指標</th>
              <th scope="col" aria-current={activeScenario === "rules" ? "true" : undefined}>
                既存ルールのみ
              </th>
              <th scope="col" aria-current={activeScenario === "hybrid" ? "true" : undefined}>
                ルール＋AI
              </th>
            </tr>
          </thead>
          <tbody>
            {ROWS.map((row) => (
              <tr key={row.label}>
                <th scope="row">{row.label}</th>
                <td className={activeScenario === "rules" ? "is-active-scenario" : undefined}>
                  {row.format(comparison.rules)}
                </td>
                <td className={activeScenario === "hybrid" ? "is-active-scenario" : undefined}>
                  {row.format(comparison.hybrid)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="comparison-message">{comparison.message}</p>
    </section>
  );
}

export default ComparisonCard;
