import type { ReactNode } from "react";

export type BadgeTone = "red" | "orange" | "yellow" | "blue" | "green" | "gray";

interface BadgeProps {
  tone: BadgeTone;
  children: ReactNode;
}

function Badge({ tone, children }: BadgeProps) {
  return <span className={`badge badge-tone-${tone}`}>{children}</span>;
}

export function priorityTone(priority: string): BadgeTone {
  switch (priority) {
    case "最優先":
      return "red";
    case "高":
      return "orange";
    case "中":
      return "blue";
    default:
      return "gray";
  }
}

export function statusTone(status: string): BadgeTone {
  switch (status) {
    case "未着手":
      return "gray";
    case "調査中":
      return "yellow";
    default:
      return "green";
  }
}

export function actionTone(action: string): BadgeTone {
  switch (action) {
    case "拒否":
      return "red";
    case "保留":
      return "orange";
    case "ステップアップ認証":
      return "yellow";
    default:
      return "green";
  }
}

export default Badge;
