import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { FeedbackSummaryPanel } from "./FeedbackSummaryPanel";
import type { FeedbackSummaryResponse, RecommendedNextAction, SampleOutcome } from "../types";

function makeNextAction(overrides: Partial<RecommendedNextAction> = {}): RecommendedNextAction {
  return {
    type: "類似顧客へ展開",
    label: "同様の利用低下パターンを持つ顧客への展開候補",
    reason: "クーポン利用の後に30日以内に利用再開となったため",
    next_review_timing: "30日後に継続利用を確認",
    ...overrides,
  };
}

function makeOutcome(overrides: Partial<SampleOutcome> = {}): SampleOutcome {
  return {
    customer_id: "C045",
    display_name: "顧客 045",
    campaign_status: "実施済み",
    customer_response: "クーポン利用",
    usage_recovery_status: "30日以内に利用再開",
    observed_at: "2026-07-15",
    is_sample: true,
    decision: null,
    selected_action: null,
    comment: null,
    decided_at: null,
    recommended_next_action: makeNextAction(),
    ...overrides,
  };
}

function makeSummary(overrides: Partial<FeedbackSummaryResponse> = {}): FeedbackSummaryResponse {
  return {
    total_decisions: 0,
    approved_count: 0,
    modified_count: 0,
    skipped_count: 0,
    by_generation_mode: {},
    recent_decisions: [],
    sample_outcomes: [],
    improvement_summary: { expand_candidates: null, review_candidates: null, next_hypothesis: null },
    updated_at: "2026-07-16T00:00:00+00:00",
    storage_mode: "file",
    persisted: true,
    ...overrides,
  };
}

describe("FeedbackSummaryPanel", () => {
  it("施策後の反応と利用状況の見出しを表示する", () => {
    render(<FeedbackSummaryPanel summary={makeSummary({ sample_outcomes: [makeOutcome()] })} />);
    expect(screen.getByText("施策後の反応と利用状況")).toBeInTheDocument();
  });

  it("施策後の反応・利用状況・確認日を表示する", () => {
    render(
      <FeedbackSummaryPanel
        summary={makeSummary({
          sample_outcomes: [
            makeOutcome({
              customer_id: "C045",
              display_name: "顧客 045",
              customer_response: "クーポン利用",
              usage_recovery_status: "30日以内に利用再開",
              observed_at: "2026-07-15",
            }),
          ],
        })}
      />,
    );
    expect(screen.getByText("顧客 045")).toBeInTheDocument();
    expect(screen.getByText("クーポン利用")).toBeInTheDocument();
    expect(screen.getByText("30日以内に利用再開")).toBeInTheDocument();
    expect(screen.getByText(/確認日/)).toBeInTheDocument();
  });

  it("反応なし・利用再開なし・観測期間中・施策未実施を正しく表示する", () => {
    render(
      <FeedbackSummaryPanel
        summary={makeSummary({
          sample_outcomes: [
            makeOutcome({
              customer_id: "C031",
              display_name: "顧客 031",
              customer_response: "反応なし",
              usage_recovery_status: "利用再開なし",
            }),
            makeOutcome({
              customer_id: "C010",
              display_name: "顧客 010",
              customer_response: "問い合わせ",
              usage_recovery_status: "観測期間中",
            }),
            makeOutcome({
              customer_id: "C017",
              display_name: "顧客 017",
              campaign_status: "施策未実施",
              customer_response: "施策未実施",
              usage_recovery_status: "施策未実施",
            }),
          ],
        })}
      />,
    );
    expect(screen.getByText("反応なし")).toBeInTheDocument();
    expect(screen.getByText("利用再開なし")).toBeInTheDocument();
    expect(screen.getByText("観測期間中")).toBeInTheDocument();
    expect(screen.getAllByText("施策未実施").length).toBeGreaterThan(0);
  });

  it("判断が未保存の場合は「未対応」と表示し、保存済みの場合は判断内容を表示する", () => {
    render(
      <FeedbackSummaryPanel
        summary={makeSummary({
          sample_outcomes: [
            makeOutcome({ customer_id: "C045", display_name: "顧客 045", decision: null }),
            makeOutcome({
              customer_id: "C031",
              display_name: "顧客 031",
              decision: "approved",
              selected_action: "反応なし",
              comment: "承認済み",
            }),
          ],
        })}
      />,
    );
    expect(screen.getByText(/未対応/)).toBeInTheDocument();
    expect(screen.getByText(/承認済み/)).toBeInTheDocument();
  });

  it("サンプルデータが空でも画面が崩れない", () => {
    const { container } = render(<FeedbackSummaryPanel summary={makeSummary({ sample_outcomes: [] })} />);
    expect(screen.queryByText("施策後の反応と利用状況")).not.toBeInTheDocument();
    expect(container).toBeInTheDocument();
  });

  it("次の推奨判断・理由・次回確認を表示する", () => {
    render(
      <FeedbackSummaryPanel
        summary={makeSummary({
          sample_outcomes: [
            makeOutcome({
              recommended_next_action: makeNextAction({
                type: "オファー内容を変更",
                reason: "クーポン利用はあったが利用再開に至らなかったため",
                next_review_timing: "14日後に反応を再確認",
              }),
            }),
          ],
        })}
      />,
    );
    expect(screen.getByText("オファー内容を変更")).toBeInTheDocument();
    expect(screen.getByText(/クーポン利用はあったが利用再開に至らなかったため/)).toBeInTheDocument();
    expect(screen.getByText(/14日後に反応を再確認/)).toBeInTheDocument();
  });

  it("Step6の締めくくり文を一度だけ表示する", () => {
    render(<FeedbackSummaryPanel summary={makeSummary({ sample_outcomes: [makeOutcome()] })} />);
    expect(
      screen.getAllByText("担当者の判断と施策結果を基に、続ける施策、見直す施策、次に検証する内容を決定します。"),
    ).toHaveLength(1);
  });

  it("今回の改善ポイントに継続・展開候補、見直し候補、次回検証する仮説を表示する", () => {
    render(
      <FeedbackSummaryPanel
        summary={makeSummary({
          sample_outcomes: [makeOutcome()],
          improvement_summary: {
            expand_candidates: "クーポン利用で利用再開が確認できた施策は展開を検討します。",
            review_candidates: "反応がなかった施策はチャネルの見直しを検討します。",
            next_hypothesis: "接触チャネルを変えると反応率が改善するかを検証します。",
          },
        })}
      />,
    );
    expect(screen.getByText("今回の改善ポイント")).toBeInTheDocument();
    expect(screen.getByText("継続・展開候補")).toBeInTheDocument();
    expect(screen.getByText("見直し候補")).toBeInTheDocument();
    expect(screen.getByText("次回検証する仮説")).toBeInTheDocument();
  });

  it("改善ポイントが無い場合は空状態のメッセージを表示する", () => {
    render(
      <FeedbackSummaryPanel
        summary={makeSummary({
          sample_outcomes: [makeOutcome()],
          improvement_summary: { expand_candidates: null, review_candidates: null, next_hypothesis: null },
        })}
      />,
    );
    expect(screen.getByText(/現時点では十分な結果がありません/)).toBeInTheDocument();
  });
});
