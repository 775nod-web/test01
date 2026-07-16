import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { FeedbackSummaryPanel } from "./FeedbackSummaryPanel";
import type { FeedbackSummaryResponse, SampleOutcome } from "../types";

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
});
