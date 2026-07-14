import type { BehaviorComparisonRow } from "../../types";

interface BehaviorComparisonTableProps {
  rows: BehaviorComparisonRow[];
}

function BehaviorComparisonTable({ rows }: BehaviorComparisonTableProps) {
  return (
    <section className="card" aria-labelledby="behavior-heading">
      <h2 id="behavior-heading">顧客の通常行動との差</h2>
      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">項目</th>
              <th scope="col">今回</th>
              <th scope="col">通常</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.item}>
                <th scope="row">{row.item}</th>
                <td>{row.current_value}</td>
                <td>{row.normal_value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default BehaviorComparisonTable;
