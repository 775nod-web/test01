import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { COMMON, NAV } from "../i18n/ja";

const NAV_ITEMS = [
  { to: "/", label: NAV.executiveOverview, end: true },
  { to: "/segments", label: NAV.segmentExplorer },
  { to: "/retention-actions", label: NAV.retentionActions },
  { to: "/poc", label: NAV.poc },
];

export function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="app-shell">
      <nav className="app-nav" aria-label="Primary">
        <div className="app-nav__brand">{NAV.brand}</div>
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) => `app-nav__link${isActive ? " active" : ""}`}
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
      <main className="app-main">
        <div className="synthetic-banner" role="note">
          <span aria-hidden="true">ⓘ</span>
          {COMMON.syntheticBanner}
        </div>
        {children}
      </main>
    </div>
  );
}

export function PageHeader({ title, question }: { title: string; question: string }) {
  return (
    <div className="page-header">
      <h1>{title}</h1>
      <p className="page-header__question">{question}</p>
    </div>
  );
}
