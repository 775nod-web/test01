import type { ReactNode } from "react";

export function Collapsible({
  title,
  badge,
  defaultOpen = false,
  children,
}: {
  title: string;
  badge?: string;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  return (
    <details className="card collapsible" open={defaultOpen}>
      <summary className="collapsible__summary">
        <span className="section-title" style={{ display: "inline", margin: 0 }}>
          {title}
        </span>
        {badge && <span className="badge badge--optional">{badge}</span>}
      </summary>
      <div className="collapsible__body">{children}</div>
    </details>
  );
}
