import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { RecommendationPanel } from "./RecommendationPanel";
import type { DecisionRecord, RecommendationResponse } from "../types";
import { postDecision } from "../api/client";

vi.mock("../api/client", () => ({
  postDecision: vi.fn(),
}));

const RECOMMENDATION: RecommendationResponse = {
  customer_id: "C001",
  generation_mode: "rule_based",
  generation_mode_label: "デモ用ルールベース生成",
  model_version: "rule-based-v1",
  generated_at: "2026-07-16T00:00:00+00:00",
  summary: "テスト顧客の状況要約です。",
  actions: [
    { title: "EC再利用の案内", reason: "ECの購入額が低下しているため。" },
    { title: "施策を行わず経過観察", reason: "効果を保証しないため。" },
  ],
  cautions: ["本推奨は参考情報です。"],
  references: [{ doc_id: "kb-ec-revisit", title: "EC再訪促進メールの施策概要", type: "knowledge" }],
};

function makeDecisionRecord(overrides: Partial<DecisionRecord> = {}): DecisionRecord {
  return {
    decision_id: "D00001",
    customer_id: "C001",
    decision: "approved",
    selected_action: "EC再利用の案内",
    modified_text: null,
    comment: null,
    decided_at: "2026-07-16T00:00:00+00:00",
    generation_mode: "rule_based",
    model_version: "rule-based-v1",
    persisted: true,
    ...overrides,
  };
}

describe("RecommendationPanel", () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  it("要約・候補・注意事項・参照元・生成方式を表示する", () => {
    render(
      <RecommendationPanel
        customerId="C001"
        recommendation={RECOMMENDATION}
        onDecisionSaved={() => {}}
      />,
    );
    expect(screen.getByText("テスト顧客の状況要約です。")).toBeInTheDocument();
    expect(screen.getByText("EC再利用の案内")).toBeInTheDocument();
    expect(screen.getByText("施策を行わず経過観察")).toBeInTheDocument();
    expect(screen.getByText("本推奨は参考情報です。")).toBeInTheDocument();
    expect(screen.getByText(/EC再訪促進メールの施策概要/)).toBeInTheDocument();
    expect(screen.getByText("デモ用ルールベース生成")).toBeInTheDocument();
  });

  it("承認して保存すると完了表示になる", async () => {
    vi.mocked(postDecision).mockResolvedValue(makeDecisionRecord());

    render(
      <RecommendationPanel
        customerId="C001"
        recommendation={RECOMMENDATION}
        onDecisionSaved={() => {}}
      />,
    );

    fireEvent.click(screen.getAllByRole("radio")[0]);
    fireEvent.click(screen.getByRole("button", { name: "承認" }));
    fireEvent.click(screen.getByRole("button", { name: "判断を保存" }));

    await waitFor(() => {
      expect(screen.getByText(/判断を記録しました（承認）/)).toBeInTheDocument();
    });
    expect(postDecision).toHaveBeenCalledWith(
      "C001",
      expect.objectContaining({ decision: "approved", selected_action: "EC再利用の案内" }),
    );
  });

  it("保存に失敗した場合は日本語のエラーメッセージを表示する", async () => {
    vi.mocked(postDecision).mockRejectedValue(
      new Error("サーバーに接続できませんでした。しばらくしてから再度お試しください。"),
    );

    render(
      <RecommendationPanel
        customerId="C001"
        recommendation={RECOMMENDATION}
        onDecisionSaved={() => {}}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "見送り" }));
    fireEvent.click(screen.getByRole("button", { name: "判断を保存" }));

    await waitFor(() => {
      expect(
        screen.getByText("サーバーに接続できませんでした。しばらくしてから再度お試しください。"),
      ).toBeInTheDocument();
    });
  });

  it("永続化されなかった場合は注意書きを表示する", async () => {
    vi.mocked(postDecision).mockResolvedValue(
      makeDecisionRecord({ decision: "skipped", selected_action: null, persisted: false }),
    );

    render(
      <RecommendationPanel
        customerId="C001"
        recommendation={RECOMMENDATION}
        onDecisionSaved={() => {}}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "見送り" }));
    fireEvent.click(screen.getByRole("button", { name: "判断を保存" }));

    await waitFor(() => {
      expect(screen.getByText(/一時保存です/)).toBeInTheDocument();
    });
  });
});
