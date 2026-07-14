import type { Last7DaysSummary, TimelineEntry } from "../../types";
import { formatJpy } from "../../utils/format";

interface TimelineTableProps {
  timeline: TimelineEntry[];
  last7Days: Last7DaysSummary;
}

function TimelineTable({ timeline, last7Days }: TimelineTableProps) {
  return (
    <section className="card" aria-labelledby="timeline-heading">
      <h2 id="timeline-heading">直近24時間の取引タイムライン</h2>
      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">時刻</th>
              <th scope="col">加盟店</th>
              <th scope="col">金額</th>
              <th scope="col">地域</th>
              <th scope="col">端末</th>
              <th scope="col">判定</th>
              <th scope="col">状態</th>
            </tr>
          </thead>
          <tbody>
            {timeline.map((entry, index) => (
              <tr key={`${entry.time}-${entry.merchant}-${index}`}>
                <td>{entry.time}</td>
                <td>{entry.merchant}</td>
                <td>{formatJpy(entry.amount)}</td>
                <td>{entry.region}</td>
                <td>{entry.device}</td>
                <td>{entry.judgement}</td>
                <td>{entry.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h3 className="chart-subheading">直近7日間の要約</h3>
      <dl className="summary-grid">
        <div>
          <dt>取引件数</dt>
          <dd>{last7Days.transaction_count.toLocaleString("ja-JP")}件</dd>
        </div>
        <div>
          <dt>合計金額</dt>
          <dd>{formatJpy(last7Days.total_amount)}</dd>
        </div>
        <div>
          <dt>平均金額</dt>
          <dd>{formatJpy(last7Days.average_amount)}</dd>
        </div>
        <div>
          <dt>不正フラグ件数</dt>
          <dd>{last7Days.fraud_flagged_count.toLocaleString("ja-JP")}件</dd>
        </div>
      </dl>
    </section>
  );
}

export default TimelineTable;
