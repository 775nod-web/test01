import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";

const NAV_ITEMS = [
  { to: "/", label: "Executive Overview", end: true },
  { to: "/segments", label: "Segment Explorer" },
  { to: "/retention-actions", label: "Retention Actions" },
  { to: "/poc", label: "PoC & Future Expansion" },
];

export function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="app-shell">
      <nav className="app-nav" aria-label="Primary">
        <div className="app-nav__brand">Retention Demo</div>
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
          Synthetic demo data — no real customer or bank data. Figures marked
          "simulated" are illustrative estimates, not real financial values.
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
