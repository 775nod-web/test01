import { NavLink } from "react-router-dom";

interface GlobalNavProps {
  dataUpdatedAt: string | null;
}

const NAV_ITEMS = [
  { to: "/", label: "概況", end: true },
  { to: "/cases", label: "調査ケース", end: false },
];

function GlobalNav({ dataUpdatedAt }: GlobalNavProps) {
  return (
    <header className="global-nav">
      <div className="global-nav-inner">
        <div className="global-nav-brand">
          <span className="global-nav-brand-title">Fraud Decision Center</span>
          <span className="global-nav-brand-subtitle">不正リスクを見抜き、正常な顧客体験と事業成長を守る</span>
        </div>
        <nav aria-label="グローバルナビゲーション" className="global-nav-links">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => `global-nav-link${isActive ? " is-active" : ""}`}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="global-nav-meta">
          {dataUpdatedAt && <span className="global-nav-updated">データ更新: {dataUpdatedAt}</span>}
          <span className="badge badge-demo">デモ用</span>
        </div>
      </div>
    </header>
  );
}

export default GlobalNav;
