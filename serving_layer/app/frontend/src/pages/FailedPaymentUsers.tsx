import { useState, type CSSProperties, type ReactNode } from "react";
import { api } from "../api/client";
import { ErrorView, LoadingView } from "../components/StateViews";
import { StatusBadge } from "../components/StatusBadge";
import { useAsyncData } from "../hooks/useAsyncData";
import { gridline, ink, uiPastel } from "../theme/colors";

type RiskFilter = "all" | "high" | "low";

export function FailedPaymentUsers() {
  const [risk, setRisk] = useState<RiskFilter>("high");
  const [planType, setPlanType] = useState<string>("");
  const [userSegment, setUserSegment] = useState<string>("");

  const state = useAsyncData(
    () => api.getFailedPaymentUsers(risk, planType || undefined, userSegment || undefined),
    [risk, planType, userSegment],
  );

  return (
    <div>
      <header style={{ marginBottom: 20 }}>
        <h1 style={{ fontSize: 22, color: ink.primary, margin: 0 }}>要フォローアップ顧客</h1>
        <p style={{ fontSize: 13, color: ink.secondary, margin: "4px 0 0" }}>
          決済失敗が発生しているユーザーを優先度順に表示し、CS・営業のアクションリストとして使う
        </p>
      </header>

      <div style={{ display: "flex", gap: 12, marginBottom: 20, flexWrap: "wrap" }}>
        <FilterGroup label="解約リスク">
          {(["high", "low", "all"] as RiskFilter[]).map((r) => (
            <FilterButton key={r} active={risk === r} onClick={() => setRisk(r)}>
              {r === "high" ? "高リスクのみ" : r === "low" ? "低リスクのみ" : "すべて"}
            </FilterButton>
          ))}
        </FilterGroup>

        <FilterGroup label="プラン">
          <select value={planType} onChange={(e) => setPlanType(e.target.value)} style={selectStyle}>
            <option value="">すべて</option>
            <option value="starter">starter</option>
            <option value="pro">pro</option>
            <option value="enterprise">enterprise</option>
          </select>
        </FilterGroup>

        <FilterGroup label="セグメント">
          <select value={userSegment} onChange={(e) => setUserSegment(e.target.value)} style={selectStyle}>
            <option value="">すべて</option>
            <option value="individual">individual</option>
            <option value="smb">smb</option>
            <option value="enterprise">enterprise</option>
          </select>
        </FilterGroup>
      </div>

      {state.status === "loading" && <LoadingView />}
      {state.status === "error" && <ErrorView message={state.error} />}
      {state.status === "success" && (
        <section style={{ background: "#ffffff", borderRadius: 14, padding: "8px 0", border: "1px solid rgba(11,11,11,0.08)" }}>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ textAlign: "left", color: ink.muted, borderBottom: `1px solid ${gridline}` }}>
                  <th style={th}>ユーザーID</th>
                  <th style={th}>リスク</th>
                  <th style={th}>プラン</th>
                  <th style={th}>セグメント</th>
                  <th style={th}>国</th>
                  <th style={th}>アクティブ</th>
                  <th style={th}>失敗回数</th>
                  <th style={th}>成功回数</th>
                  <th style={th}>直近決済日</th>
                  <th style={th}>直近ステータス</th>
                  <th style={th}>直近金額</th>
                  <th style={th}>直近解約クリック</th>
                </tr>
              </thead>
              <tbody>
                {state.data.map((u) => (
                  <tr key={u.user_id} style={{ borderBottom: `1px solid ${gridline}` }}>
                    <td style={{ ...td, fontWeight: 600 }}>{u.user_id}</td>
                    <td style={td}>
                      <StatusBadge isHighRisk={u.churn_risk_flag} />
                    </td>
                    <td style={td}>{u.plan_type ?? "—"}</td>
                    <td style={td}>{u.user_segment ?? "—"}</td>
                    <td style={td}>{u.country_code ?? "—"}</td>
                    <td style={td}>{u.is_active == null ? "—" : u.is_active ? "有効" : "無効"}</td>
                    <td style={{ ...td, fontWeight: 700 }}>{u.total_failed_count}</td>
                    <td style={td}>{u.total_success_count}</td>
                    <td style={td}>{u.latest_payment_date ?? "—"}</td>
                    <td style={td}>{u.latest_payment_status ?? "—"}</td>
                    <td style={td}>{u.latest_amount != null ? `¥${Math.round(u.latest_amount).toLocaleString()}` : "—"}</td>
                    <td style={td}>
                      {u.has_recent_cancel_click ? (
                        <span style={{ color: uiPastel.red, fontWeight: 600 }}>あり</span>
                      ) : (
                        "なし"
                      )}
                    </td>
                  </tr>
                ))}
                {state.data.length === 0 && (
                  <tr>
                    <td style={td} colSpan={12}>
                      該当するユーザーはいません。
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}

function FilterGroup({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <div style={{ fontSize: 11, color: ink.muted, marginBottom: 4 }}>{label}</div>
      <div style={{ display: "flex", gap: 6 }}>{children}</div>
    </div>
  );
}

function FilterButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: "6px 12px",
        borderRadius: 999,
        border: "none",
        cursor: "pointer",
        fontSize: 12,
        fontWeight: 600,
        background: active ? uiPastel.orange : "#ffffff",
        color: ink.primary,
      }}
    >
      {children}
    </button>
  );
}

const selectStyle: CSSProperties = {
  padding: "6px 10px",
  borderRadius: 8,
  border: `1px solid ${gridline}`,
  fontSize: 12,
};

const th: CSSProperties = { padding: "10px 14px", fontWeight: 600, whiteSpace: "nowrap" };
const td: CSSProperties = { padding: "10px 14px", whiteSpace: "nowrap" };
