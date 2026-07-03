import { ink } from "../theme/colors";

export function LoadingView({ label = "読み込み中..." }: { label?: string }) {
  return <div style={{ padding: 24, color: ink.muted, fontSize: 14 }}>{label}</div>;
}

export function ErrorView({ message }: { message: string }) {
  return (
    <div
      style={{
        padding: 16,
        borderRadius: 10,
        background: "#fdecea",
        color: "#7a1f1a",
        fontSize: 14,
        border: "1px solid #f3c7c2",
      }}
    >
      データの取得に失敗しました: {message}
    </div>
  );
}
