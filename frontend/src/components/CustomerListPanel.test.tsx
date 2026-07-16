import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CustomerListPanel } from "./CustomerListPanel";
import type { CustomerSummary } from "../types";

const CUSTOMERS: CustomerSummary[] = [
  {
    customer_id: "C001",
    display_name: "顧客 001",
    risk_band: "high",
    risk_band_label: "高",
    churn_probability: 0.9,
    service_count: 2,
    previous_service_count: 3,
    top_reason: "QR決済・カードの利用額が前期比-50%低下しています",
  },
  {
    customer_id: "C002",
    display_name: "顧客 002",
    risk_band: "low",
    risk_band_label: "低",
    churn_probability: 0.1,
    service_count: 3,
    previous_service_count: 3,
    top_reason: null,
  },
];

describe("CustomerListPanel", () => {
  it("顧客一覧を表示する", () => {
    render(
      <CustomerListPanel customers={CUSTOMERS} selectedCustomerId={null} onSelect={() => {}} />,
    );
    expect(screen.getByText("顧客 001")).toBeInTheDocument();
    expect(screen.getByText("顧客 002")).toBeInTheDocument();
    expect(screen.getByText(/休眠確率 90%/)).toBeInTheDocument();
  });

  it("顧客をクリックするとonSelectが呼ばれる", () => {
    const onSelect = vi.fn();
    render(
      <CustomerListPanel customers={CUSTOMERS} selectedCustomerId={null} onSelect={onSelect} />,
    );
    fireEvent.click(screen.getByText("顧客 002"));
    expect(onSelect).toHaveBeenCalledWith("C002");
  });

  it("選択中の顧客にaria-pressedが付与される", () => {
    render(
      <CustomerListPanel customers={CUSTOMERS} selectedCustomerId="C001" onSelect={() => {}} />,
    );
    const buttons = screen.getAllByRole("button");
    expect(buttons[0]).toHaveAttribute("aria-pressed", "true");
    expect(buttons[1]).toHaveAttribute("aria-pressed", "false");
  });
});
