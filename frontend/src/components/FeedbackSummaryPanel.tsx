import type { FeedbackSummaryResponse } from "../types";

const DECISION_LABEL: Record<string, string> = {
  approved: "承認",
  modified: "修正",
  skipped: "見送り",
};

export function FeedbackSummaryPanel({ summary }: { summary: FeedbackSummaryResponse }) {
  return (
    <div className="feedback-summary">
      <div className="feedback-summary__counts">
        <div className="feedback-summary__count">
          <span className="feedback-summary__count-value">{summary.approved_count}</span>
          <span className="feedback-summary__count-label">承認</span>
        </div>
        <div className="feedback-summary__count">
          <span className="feedback-summary__count-value">{summary.modified_count}</span>
          <span className="feedback-summary__count-label">修正</span>
        </div>
        <div className="feedback-summary__count">
          <span className="feedback-summary__count-value">{summary.skipped_count}</span>
          <span className="feedback-summary__count-label">見送り</span>
        </div>
      </div>

      <p className="feedback-summary__explanation">
        承認・修正・見送りの判断は、次の顧客選定や施策改善、モデルの見直しへ活用する想定のデータとして記録されます。
      </p>

      {summary.recent_decisions.length > 0 && (
        <ul className="feedback-summary__recent">
          {summary.recent_decisions.map((decision, index) => (
            <li key={`${decision.customer_id}-${decision.decided_at}-${index}`}>
              {decision.display_name} ・ {DECISION_LABEL[decision.decision] ?? decision.decision}
              {decision.selected_action ? `（${decision.selected_action}）` : ""} ・{" "}
              {decision.generation_mode_label}
            </li>
          ))}
        </ul>
      )}

      <p className="feedback-summary__production-note">本番化時に追加：{summary.note}</p>
    </div>
  );
}
