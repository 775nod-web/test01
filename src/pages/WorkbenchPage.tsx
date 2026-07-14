import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, getCases, type CaseListParams } from "../api";
import Badge, { actionTone, priorityTone, statusTone } from "../components/common/Badge";
import WorkbenchFilterBar from "../components/workbench/WorkbenchFilterBar";
import type { CaseSummary } from "../types";
import { formatJpy } from "../utils/format";

type LoadState = "loading" | "success" | "error";

function WorkbenchPage() {
  const navigate = useNavigate();
  const [filters, setFilters] = useState<CaseListParams>({});
  const [state, setState] = useState<LoadState>("loading");
  const [items, setItems] = useState<CaseSummary[]>([]);
  const [errorMessage, setErrorMessage] = useState("");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function load(nextFilters: CaseListParams) {
    setState("loading");
    getCases(nextFilters)
      .then((result) => {
        setItems(result.items);
        setState("success");
      })
      .catch((error: unknown) => {
        setErrorMessage(error instanceof ApiError ? error.message : "ケース一覧の取得に失敗しました。");
        setState("error");
      });
  }

  useEffect(() => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }
    debounceRef.current = setTimeout(() => {
      load(filters);
    }, 250);
    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters]);

  return (
    <div className="workbench-page">
      <div className="page-header">
        <h1>不正調査ワークベンチ</h1>
        <p className="page-description">高リスク案件を優先し、取引の背景と判定理由を一画面で確認します。</p>
      </div>

      <WorkbenchFilterBar filters={filters} onChange={setFilters} />

      {state === "loading" && (
        <div className="card" role="status">
          <span className="badge badge-loading">読み込み中</span>
          <p>ケース一覧を取得しています…</p>
        </div>
      )}

      {state === "error" && (
        <div className="card" role="alert">
          <span className="badge badge-tone-red">エラー</span>
          <p>{errorMessage}</p>
          <button type="button" onClick={() => load(filters)}>
            再試行
          </button>
        </div>
      )}

      {state === "success" && (
        <section className="card">
          <p className="chart-caption">{items.length}件のケースが該当しました。</p>
          {items.length === 0 ? (
            <p className="empty-state">条件に一致するケースがありません。フィルターを変更してください。</p>
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
                    <th scope="col">関連取引数</th>
                    <th scope="col">ステータス</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((row) => (
                    <tr
                      key={row.transaction_id}
                      tabIndex={0}
                      role="button"
                      aria-label={`${row.transaction_id}の調査詳細を開く`}
                      className="clickable-row"
                      onClick={() => navigate(`/cases/${encodeURIComponent(row.transaction_id)}`)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          navigate(`/cases/${encodeURIComponent(row.transaction_id)}`);
                        }
                      }}
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
                      <td>{row.related_transaction_count}件</td>
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
      )}
    </div>
  );
}

export default WorkbenchPage;
