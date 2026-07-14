import type { ValueRiskMatrixItem } from "../types";

const VALUE_ORDER = ["High", "Medium", "Low"] as const;
const RISK_ORDER = ["High", "Medium", "Low"] as const;

// Sequential single-hue (blue) hue scale by magnitude, rendered as a real
// HTML table so screen readers and the "no color alone" rule are satisfied
// by construction — every cell shows its count as text regardless of shade.
function shadeFor(count: number, max: number): string {
  if (max === 0) return "#ffffff";
  const t = count / max;
  if (t === 0) return "#ffffff";
  if (t < 0.15) return "#eaf1fd";
  if (t < 0.35) return "#cfe0fb";
  if (t < 0.6) return "#a8c8f7";
  if (t < 0.85) return "#7ba7f2";
  return "#4285f4";
}

export function ValueRiskMatrix({ data }: { data: ValueRiskMatrixItem[] }) {
  const lookup = new Map<string, ValueRiskMatrixItem>();
  for (const item of data) {
    lookup.set(`${item.value_segment}|${item.risk_segment}`, item);
  }
  const max = Math.max(...data.map((d) => d.customer_count), 1);

  return (
    <table className="data-table matrix-table" aria-label="Customer value versus churn risk matrix">
      <thead>
        <tr>
          <th scope="col">Value \ Risk</th>
          {RISK_ORDER.map((r) => (
            <th scope="col" key={r}>
              {r}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {VALUE_ORDER.map((v) => (
          <tr key={v}>
            <th scope="row">{v} value</th>
            {RISK_ORDER.map((r) => {
              const cell = lookup.get(`${v}|${r}`);
              const count = cell?.customer_count ?? 0;
              return (
                <td key={r} style={{ background: shadeFor(count, max) }}>
                  <span className="matrix-count">{count}</span>
                  {cell && cell.estimated_value_at_risk_simulated > 0 && (
                    <span className="matrix-sub">
                      ${Math.round(cell.estimated_value_at_risk_simulated).toLocaleString()} sim.
                    </span>
                  )}
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
