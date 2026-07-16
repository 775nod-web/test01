import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { RiskBadge } from "./RiskBadge";

describe("RiskBadge", () => {
  it("色だけに頼らず、ラベルとアイコンの両方でリスク帯を示す", () => {
    render(<RiskBadge band="high" label="高" />);
    const badge = screen.getByText(/高リスク/);
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain("badge--risk-high");
  });

  it.each([
    ["high", "高"],
    ["medium", "中"],
    ["low", "低"],
  ] as const)("%sバンドで「%sリスク」を表示する", (band, label) => {
    render(<RiskBadge band={band} label={label} />);
    expect(screen.getByText(`${label}リスク`)).toBeInTheDocument();
  });
});
