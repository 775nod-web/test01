import type { CSSProperties } from "react";
import { api } from "../api/client";
import { ErrorView, LoadingView } from "../components/StateViews";
import { useAsyncData } from "../hooks/useAsyncData";
import { gridline, ink, status } from "../theme/colors";
import type { DataQualitySummary as DqRow } from "../api/types";

function severityColor(failedRate: number | null): string {
  if (failedRate == null) return ink.muted;
  if (failedRate >= 0.1) return status.critical;
  if (failedRate >= 0.02) return status.warning;
  return status.good;
}

function severityLabel(failedRate: number | null): string {
  if (failedRate == null) return "データなし";
  if (failedRate >= 0.1) return "重大";
  if (failedRate >= 0.02) return "要注意";
  return "正常";
}

export function DataQualitySummary() {
  const state = useAsyncData(() => api.getDataQualitySummary(14), []);

  return (
    <div>
      <header style={{ marginBottom: 20 }}>
        <h1 style={{ fontSize: 22, color: ink.primary, margin: 0 }}>データ品質サマリー</h1>
        <p style={{ fontSize: 13, color: ink.secondary, margin: "4px 0 0" }}>
          Bronze/Silver処理で検出された品質課題を日次でモニタリングする（データエンジニアリング向け）
        </p>
      </header>

      {state.status === "loading" && <LoadingView />}
      {state.status === "error" && <ErrorView message={state.error} />}
      {state.status === "success" && <DqTable rows={state.data} />}
    </div>
  );
}

function DqTable({ rows }: { rows: DqRow[] }) {
  const sorted = [...rows].sort((a, b) => {
    if (a.run_date !== b.run_date) return a.run_date < b.run_date ? 1 : -1;
    return (b.failed_rate ?? 0) - (a.failed_rate ?? 0);
  });

  return (
    <section style={{ background: "#ffffff", borderRadius: 14, padding: "8px 0", border: "1px solid rgba(11,11,11,0.08)" }}>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ textAlign: "left", color: ink.muted, borderBottom: `1px solid ${gridline}` }}>
              <th style={th}>実行日</th>
              <th style={th}>対象テーブル</th>
              <th style={th}>チェック名</th>
              <th style={th}>失敗件数</th>
              <th style={th}>チェック対象件数</th>
              <th style={th}>失敗率</th>
              <th style={th}>ステータス</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((r) => (
              <tr key={`${r.run_date}-${r.source_table}-${r.dq_check_name}`} style={{ borderBottom: `1px solid ${gridline}` }}>
                <td style={td}>{r.run_date}</td>
                <td style={{ ...td, fontWeight: 600 }}>{r.source_table}</td>
                <td style={td}>{r.dq_check_name}</td>
                <td style={td}>{r.failed_record_count.toLocaleString()}</td>
                <td style={td}>{r.checked_record_count.toLocaleString()}</td>
                <td style={{ ...td, fontWeight: 700, color: severityColor(r.failed_rate) }}>
                  {r.failed_rate != null ? `${(r.failed_rate * 100).toFixed(2)}%` : "—"}
                </td>
                <td style={td}>
                  <span
                    style={{
                      display: "inline-block",
                      padding: "3px 10px",
                      borderRadius: 999,
                      fontSize: 12,
                      fontWeight: 600,
                      color: "#ffffff",
                      background: severityColor(r.failed_rate),
                    }}
                  >
                    {severityLabel(r.failed_rate)}
                  </span>
                </td>
              </tr>
            ))}
            {sorted.length === 0 && (
              <tr>
                <td style={td} colSpan={7}>
                  直近期間のデータ品質レコードはありません。
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

const th: CSSProperties = { padding: "10px 14px", fontWeight: 600, whiteSpace: "nowrap" };
const td: CSSProperties = { padding: "10px 14px", whiteSpace: "nowrap" };
