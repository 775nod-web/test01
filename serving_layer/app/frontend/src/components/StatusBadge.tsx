import { status } from "../theme/colors";

interface StatusBadgeProps {
  isHighRisk: boolean;
}

/** 色だけに依存しないよう、常にラベルを併記するバッジ。 */
export function StatusBadge({ isHighRisk }: StatusBadgeProps) {
  const color = isHighRisk ? status.critical : status.good;
  const label = isHighRisk ? "要フォローアップ" : "低リスク";
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        padding: "3px 10px",
        borderRadius: 999,
        fontSize: 12,
        fontWeight: 600,
        color: "#ffffff",
        background: color,
      }}
    >
      {label}
    </span>
  );
}
