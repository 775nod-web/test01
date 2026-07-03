import { NavLink, Outlet } from "react-router-dom";
import { surface, ink, uiPastel } from "../theme/colors";

const NAV_ITEMS = [
  { to: "/", label: "経営KPI", accent: uiPastel.blue, description: "経営層向け" },
  { to: "/sales-per-plan", label: "プラン別売上", accent: uiPastel.green, description: "事業企画・プロダクト向け" },
  { to: "/failed-payment-users", label: "要フォローアップ顧客", accent: uiPastel.orange, description: "CS・営業向け" },
  { to: "/data-quality", label: "データ品質", accent: uiPastel.purple, description: "データエンジニアリング向け" },
];

export function Layout() {
  return (
    <div style={{ display: "flex", minHeight: "100vh", background: surface.page }}>
      <aside
        style={{
          width: 240,
          flexShrink: 0,
          background: surface.sidebar,
          borderRight: `1px solid ${surface.border}`,
          padding: "24px 16px",
        }}
      >
        <div style={{ fontWeight: 700, fontSize: 16, color: ink.primary, marginBottom: 4 }}>
          Gold Layer Serving
        </div>
        <div style={{ fontSize: 12, color: ink.muted, marginBottom: 24 }}>Databricks Apps</div>
        <nav style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              style={({ isActive }) => ({
                display: "block",
                padding: "10px 12px",
                borderRadius: 10,
                textDecoration: "none",
                color: ink.primary,
                background: isActive ? item.accent : "transparent",
                fontWeight: isActive ? 600 : 500,
                transition: "background 0.15s ease",
              })}
            >
              <div style={{ fontSize: 14 }}>{item.label}</div>
              <div style={{ fontSize: 11, color: ink.secondary }}>{item.description}</div>
            </NavLink>
          ))}
        </nav>
      </aside>
      <main style={{ flex: 1, padding: "28px 32px", minWidth: 0 }}>
        <Outlet />
      </main>
    </div>
  );
}
