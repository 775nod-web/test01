import { useEffect, useState } from "react";
import { fetchQuarantineReport, fetchQuarantineSummary, triggerReconciliation } from "../api/client";
import type { QuarantineReportRow, QuarantineSummaryRow } from "../types";

export function DataQualityView() {
  const [report, setReport] = useState<QuarantineReportRow[]>([]);
  const [summary, setSummary] = useState<QuarantineSummaryRow[]>([]);
  const [issueFilter, setIssueFilter] = useState<string>("");
  const [reconcileStatus, setReconcileStatus] = useState<string>("");

  useEffect(() => {
    fetchQuarantineReport(issueFilter || undefined).then(setReport).catch(console.error);
  }, [issueFilter]);

  useEffect(() => {
    fetchQuarantineSummary().then(setSummary).catch(console.error);
  }, []);

  async function handleReconcile() {
    setReconcileStatus("実行中...");
    try {
      const result = await triggerReconciliation();
      setReconcileStatus(
        result.triggered ? `再照合ジョブを実行しました（run_id: ${result.run_id}）` : `未実行: ${result.reason}`
      );
    } catch (e) {
      setReconcileStatus("再照合の実行に失敗しました");
    }
  }

  return (
    <div>
      <h2>データ品質ビュー</h2>

      <div className="card">
        <h3>quarantine率の推移（issue_type別・日次件数）</h3>
        <table>
          <thead>
            <tr>
              <th>日付</th>
              <th>未登録種別</th>
              <th>件数</th>
            </tr>
          </thead>
          <tbody>
            {summary.map((row, i) => (
              <tr key={i}>
                <td>{row.report_date}</td>
                <td><span className="badge-warning">{row.issue_type}</span></td>
                <td>{row.unregistered_count.toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h3>マスター未登録取引レポート</h3>
        <div style={{ marginBottom: 12 }}>
          <select value={issueFilter} onChange={(e) => setIssueFilter(e.target.value)}>
            <option value="">すべて</option>
            <option value="store_id未登録">store_id未登録</option>
            <option value="product_id未登録">product_id未登録</option>
            <option value="両方">両方</option>
          </select>
          <button onClick={handleReconcile} style={{ marginLeft: 12 }} className="tab-button">
            再照合を実行
          </button>
          {reconcileStatus && <span style={{ marginLeft: 12, fontSize: 13 }}>{reconcileStatus}</span>}
        </div>
        <table>
          <thead>
            <tr>
              <th>取引ID</th>
              <th>種別</th>
              <th>店舗ID</th>
              <th>商品ID</th>
              <th>売上金額</th>
            </tr>
          </thead>
          <tbody>
            {report.map((row) => (
              <tr key={row.transaction_id}>
                <td>{row.transaction_id}</td>
                <td><span className="badge-warning">{row.issue_type}</span></td>
                <td>{row.store_id ?? "-"}</td>
                <td>{row.product_id ?? "-"}</td>
                <td>{row.sales_amount?.toLocaleString() ?? "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
