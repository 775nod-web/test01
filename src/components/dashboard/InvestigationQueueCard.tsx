import type { InvestigationQueueSummary, Priority } from "../../types";
import Badge, { priorityTone } from "../common/Badge";

interface InvestigationQueueCardProps {
  queue: InvestigationQueueSummary;
}

const PRIORITY_ORDER: Priority[] = ["最優先", "高", "中", "低"];

function InvestigationQueueCard({ queue }: InvestigationQueueCardProps) {
  const maxCount = Math.max(1, ...PRIORITY_ORDER.map((p) => queue.by_priority[p] ?? 0));

  return (
    <section className="card" aria-labelledby="queue-heading">
      <h2 id="queue-heading">調査キューの状況</h2>
      <div className="queue-stats">
        <div className="queue-stat">
          <span className="queue-stat-value">{queue.pending_count}</span>
          <span className="queue-stat-label">未着手</span>
        </div>
        <div className="queue-stat">
          <span className="queue-stat-value">{queue.in_progress_count}</span>
          <span className="queue-stat-label">調査中</span>
        </div>
        <div className="queue-stat">
          <span className="queue-stat-value">{queue.completed_count}</span>
          <span className="queue-stat-label">完了</span>
        </div>
      </div>

      <h3 className="chart-subheading">優先度別の未対応件数</h3>
      <ul className="queue-priority-list">
        {PRIORITY_ORDER.map((priority) => {
          const count = queue.by_priority[priority] ?? 0;
          return (
            <li key={priority} className="queue-priority-row">
              <Badge tone={priorityTone(priority)}>{priority}</Badge>
              <div className="queue-priority-bar-track">
                <div
                  className="queue-priority-bar-fill"
                  style={{ width: `${(count / maxCount) * 100}%` }}
                />
              </div>
              <span className="queue-priority-count">{count}件</span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export default InvestigationQueueCard;
