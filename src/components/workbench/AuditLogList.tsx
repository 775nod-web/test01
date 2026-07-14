import type { AuditLogEntry } from "../../types";

interface AuditLogListProps {
  log: AuditLogEntry[];
}

function AuditLogList({ log }: AuditLogListProps) {
  return (
    <div>
      <h3 className="chart-subheading">操作履歴（デモ用監査情報）</h3>
      <ul className="audit-log-list">
        {log.map((entry, index) => (
          <li key={`${entry.timestamp}-${index}`}>
            <span className="audit-log-time">{entry.timestamp}</span>
            <span className="audit-log-actor">{entry.actor}</span>
            <span className="audit-log-action">{entry.action}</span>
          </li>
        ))}
      </ul>
      <p className="meta-line">
        本デモの操作履歴は簡易表示です。「完全な監査機能」ではなく、本番構成ではUnity
        Catalog等のガバナンス機能と連携する想定です。
      </p>
    </div>
  );
}

export default AuditLogList;
