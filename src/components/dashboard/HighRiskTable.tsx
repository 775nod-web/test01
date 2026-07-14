import type { KeyboardEvent } from "react";
import { useNavigate } from "react-router-dom";
import type { HighRiskTransactionRow } from "../../types";
import { formatJpy } from "../../utils/format";
import Badge, { actionTone, priorityTone, statusTone } from "../common/Badge";

interface HighRiskTableProps {
  rows: HighRiskTransactionRow[];
}

function HighRiskTable({ rows }: HighRiskTableProps) {
  const navigate = useNavigate();

  function goToDetail(transactionId: string) {
    navigate(`/cases/${encodeURIComponent(transactionId)}`);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTableRowElement>, transactionId: string) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      goToDetail(transactionId);
    }
  }

  return (
    <section className="card" aria-labelledby="high-risk-heading">
      <h2 id="high-risk-heading">高リスク取引一覧</h2>
      <p className="chart-caption">行を選択すると、調査ワークベンチで詳細を確認できます。</p>

      {rows.length === 0 ? (
        <p className="empty-state">該当する高リスク取引はありません。</p>
      ) : (
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">優先度</th>
                <th scope="col">取引ID</th>
                <th scope="col">リスクスコア</th>
                <th scope="col">推奨アクション</th>
                <th scope="col">金額</th>
                <th scope="col">加盟店</th>
                <th scope="col">日時</th>
                <th scope="col">ステータス</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr
                  key={row.transaction_id}
                  tabIndex={0}
                  role="button"
                  aria-label={`${row.transaction_id}の調査詳細を開く`}
                  className="clickable-row"
                  onClick={() => goToDetail(row.transaction_id)}
                  onKeyDown={(e) => handleKeyDown(e, row.transaction_id)}
                >
                  <td>
                    <Badge tone={priorityTone(row.priority)}>{row.priority}</Badge>
                  </td>
                  <td className="mono">{row.transaction_id}</td>
                  <td>{row.risk_score.toFixed(2)}</td>
                  <td>
                    <Badge tone={actionTone(row.recommended_action)}>{row.recommended_action}</Badge>
                  </td>
                  <td>{formatJpy(row.amount)}</td>
                  <td>{row.merchant}</td>
                  <td>{row.transaction_datetime}</td>
                  <td>
                    <Badge tone={statusTone(row.status)}>{row.status}</Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export default HighRiskTable;
