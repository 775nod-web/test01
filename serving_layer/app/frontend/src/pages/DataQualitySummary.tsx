import type { CSSProperties } from "react";
import { api } from "../api/client";
import { ErrorView, LoadingView } from "../components/StateViews";
import { useAsyncData } from "../hooks/useAsyncData";
import { gridline, ink, status } from "../theme/colors";
import type { DataQualitySummary as DqRow } from "../api/types";

function severityColor(issueRate: number | null): string {
  if (issueRate == null) return ink.muted;
  if (issueRate >= 0.1) return status.critical;
  if (issueRate >= 0.02) return status.warning;
  return status.good;
}

function severityLabel(issueRate: number | null): string {
  if (issueRate == null) return "データなし";
  if (issueRate >= 0.1) return "重大";
  if (issueRate >= 0.02) return "要注意";
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
    return (b.issue_rate ?? 0) - (a.issue_rate ?? 0);
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
              <th style={th}>問題件数</th>
              <th style={th}>対象レコード数</th>
              <th style={th}>問題率</th>
              <th style={th}>ステータス</th>
              <th style={th}>詳細</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((r) => (
              <tr key={`${r.run_date}-${r.source_table}-${r.dq_check_name}`} style={{ borderBottom: `1px solid ${gridline}` }}>
                <td style={td}>{r.run_date}</td>
                <td style={{ ...td, fontWeight: 600 }}>{r.source_table}</td>
                <td style={td}>{r.dq_check_name}</td>
                <td style={td}>{r.issue_count.toLocaleString()}</td>
                <td style={td}>{r.total_records.toLocaleString()}</td>
                <td style={{ ...td, fontWeight: 700, color: severityColor(r.issue_rate) }}>
                  {r.issue_rate != null ? `${(r.issue_rate * 100).toFixed(2)}%` : "—"}
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
                      background: severityColor(r.issue_rate),
                    }}
                  >
                    {severityLabel(r.issue_rate)}
                  </span>
                </td>
                <td style={{ ...td, whiteSpace: "normal", color: ink.secondary, maxWidth: 320 }}>{r.description ?? "—"}</td>
              </tr>
            ))}
            {sorted.length === 0 && (
              <tr>
                <td style={td} colSpan={8}>
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
