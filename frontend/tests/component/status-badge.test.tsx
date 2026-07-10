import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { PaymentStatusBadge } from "@/components/status-badge";

/**
 * specs/03-maintenance-billing/frontend.md §4.1: "Dues DataTable renders the
 * correct Badge variant (success/warning/destructive) for each of
 * Paid/Pending/Overdue statuses — snapshot/DOM assertion on the class/token
 * used, not just text." Asserted directly against `PaymentStatusBadge` (the
 * shared mapping `dues-data-table.tsx` renders through), per
 * specs/00-architecture-and-standards.md §3.1's rule that these three
 * tokens are never reused for other semantics.
 */
describe("PaymentStatusBadge", () => {
  it("renders the success token for Paid", () => {
    const { container } = render(<PaymentStatusBadge status="Paid" />);
    expect(container.querySelector(".bg-success")).not.toBeNull();
  });

  it("renders the warning token for Pending", () => {
    const { container } = render(<PaymentStatusBadge status="Pending" />);
    expect(container.querySelector(".bg-warning")).not.toBeNull();
  });

  it("renders the destructive token for Overdue", () => {
    const { container } = render(<PaymentStatusBadge status="Overdue" />);
    expect(container.querySelector(".bg-destructive")).not.toBeNull();
  });

  it("never reuses the success/warning/destructive tokens for Vacant", () => {
    const { container } = render(<PaymentStatusBadge status="Vacant" />);
    expect(container.querySelector(".bg-success")).toBeNull();
    expect(container.querySelector(".bg-warning")).toBeNull();
    expect(container.querySelector(".bg-destructive")).toBeNull();
  });
});
