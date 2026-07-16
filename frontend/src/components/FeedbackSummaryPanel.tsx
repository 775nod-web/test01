import type { FeedbackSummaryResponse, SampleOutcome } from "../types";

const DECISION_LABEL: Record<string, string> = {
  approved: "承認",
  modified: "修正",
  skipped: "見送り",
};

const RESPONSE_STATUS_CLASS: Record<string, string> = {
  メール開封: "outcome-badge--engaged",
  案内ページ閲覧: "outcome-badge--engaged",
  クーポン利用: "outcome-badge--engaged",
  問い合わせ: "outcome-badge--engaged",
  反応なし: "outcome-badge--neutral",
  施策未実施: "outcome-badge--neutral",
};

const RECOVERY_STATUS_CLASS: Record<string, string> = {
  "30日以内に利用再開": "outcome-badge--recovered",
  一部サービスで利用再開: "outcome-badge--recovered",
  観測期間中: "outcome-badge--observing",
  利用再開なし: "outcome-badge--neutral",
  施策未実施: "outcome-badge--neutral",
};

function formatObservedAt(dateStr: string): string {
  try {
    return new Date(dateStr).toLocaleDateString("ja-JP");
  } catch {
    return dateStr;
  }
}

function SampleOutcomeCard({ outcome }: { outcome: SampleOutcome }) {
  const decisionLabel = outcome.decision ? (DECISION_LABEL[outcome.decision] ?? outcome.decision) : "未対応（判断未保存）";
  const nextAction = outcome.recommended_next_action;
  return (
    <li className="outcome-card">
      <p className="outcome-card__name">{outcome.display_name}</p>
      <p className="outcome-card__row">
        <span className="outcome-card__row-label">担当者判断：</span>
        {decisionLabel}
        {outcome.selected_action ? `（${outcome.selected_action}）` : ""}
        {outcome.comment ? ` ・ ${outcome.comment}` : ""}
      </p>
      <p className="outcome-card__row">
        <span className="outcome-card__row-label">施策後の反応：</span>
        <span className={`outcome-badge ${RESPONSE_STATUS_CLASS[outcome.customer_response] ?? "outcome-badge--neutral"}`}>
          {outcome.customer_response}
        </span>
      </p>
      <p className="outcome-card__row">
        <span className="outcome-card__row-label">利用状況：</span>
        <span
          className={`outcome-badge ${RECOVERY_STATUS_CLASS[outcome.usage_recovery_status] ?? "outcome-badge--neutral"}`}
        >
          {outcome.usage_recovery_status}
        </span>
        <span className="outcome-card__observed-at">（確認日：{formatObservedAt(outcome.observed_at)}）</span>
      </p>
      <p className="outcome-card__row">
        <span className="outcome-card__row-label">次の推奨判断：</span>
        <span className="outcome-badge outcome-badge--action">{nextAction.type}</span>
      </p>
      <p className="outcome-card__row outcome-card__row--reason">
        <span className="outcome-card__row-label">理由：</span>
        {nextAction.reason}
      </p>
      <p className="outcome-card__row">
        <span className="outcome-card__row-label">次回確認：</span>
        {nextAction.next_review_timing}
      </p>
    </li>
  );
}

export function FeedbackSummaryPanel({ summary }: { summary: FeedbackSummaryResponse }) {
  return (
    <div className="feedback-summary">
      {!summary.persisted && (
        <p className="feedback-summary__not-persisted">
          ⚠️
          現在、判断の保存先に書き込めないため、記録は一時的なものです（アプリ再起動で失われます）。
        </p>
      )}

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

      {summary.sample_outcomes.length > 0 && (
        <div className="feedback-summary__outcomes">
          <h3 className="feedback-summary__outcomes-title">施策後の反応と利用状況</h3>
          <ul className="feedback-summary__outcomes-list">
            {summary.sample_outcomes.map((outcome) => (
              <SampleOutcomeCard key={outcome.customer_id} outcome={outcome} />
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
