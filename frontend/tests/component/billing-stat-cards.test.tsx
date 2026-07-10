import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { BillingStatCards } from "@/components/billing/BillingStatCards";

/**
 * specs/03-maintenance-billing/frontend.md §4.1: "BillingStatCards component
 * renders correctly with zero-value props (e.g. a brand-new tower with
 * pendingCount = 0) without crashing the NumberTicker animation."
 */
describe("BillingStatCards", () => {
  it("renders without crashing when every prop is 0", () => {
    render(<BillingStatCards totalCollected={0} pendingCount={0} overdueAmount={0} />);

    expect(screen.getByText("Total Collected This Cycle")).toBeInTheDocument();
    expect(screen.getByText("Pending Count")).toBeInTheDocument();
    expect(screen.getByText("Overdue Amount")).toBeInTheDocument();
    // NumberTicker starts its animation from 0 — with a target of 0 it should
    // render "0" (or "₹0.00") immediately, never "NaN" or "undefined".
    expect(screen.queryByText(/nan/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/undefined/i)).not.toBeInTheDocument();
  });

  it("supports Module 5's tower-wide relabeling without any data-fetching of its own", () => {
    render(
      <BillingStatCards
        totalCollected={184500}
        pendingCount={12}
        overdueAmount={23400}
        labels={{ totalCollected: "Total Collected (Tower-wide)" }}
      />
    );

    expect(screen.getByText("Total Collected (Tower-wide)")).toBeInTheDocument();
  });
});
