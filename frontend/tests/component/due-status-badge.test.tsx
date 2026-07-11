import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { PaymentStatusBadge } from "@/components/status-badge";

/**
 * frontend.md Component test #4: "Status badge mapping matches Module 3's
 * convention." Module 1 already extracted the shared status-badge component
 * (components/status-badge.tsx `PaymentStatusBadge`) with exactly the
 * mapping specs/00-architecture-and-standards.md §3.1 defines — Paid =
 * success, Pending = warning, Overdue = destructive. Module 4's special
 * collection dues table (see special-collections/[id]/collection-detail-client.tsx)
 * imports this same component rather than inventing a parallel one, so this
 * test snapshot-asserts the exact class names it renders to catch drift if
 * either module's usage of the shared badge is edited independently.
 */
describe("PaymentStatusBadge", () => {
  it("renders the destructive/red badge for Overdue", () => {
    const { container } = render(<PaymentStatusBadge status="Overdue" />);
    const badge = container.firstElementChild as HTMLElement;
    expect(badge.className).toContain("bg-destructive");
    expect(badge.className).toContain("text-destructive-foreground");
    expect(badge.textContent).toBe("Overdue");
  });

  it("renders the success/green badge for Paid", () => {
    const { container } = render(<PaymentStatusBadge status="Paid" />);
    const badge = container.firstElementChild as HTMLElement;
    expect(badge.className).toContain("bg-success");
    expect(badge.className).toContain("text-success-foreground");
    expect(badge.textContent).toBe("Paid");
  });

  it("renders the warning/amber badge for Pending", () => {
    const { container } = render(<PaymentStatusBadge status="Pending" />);
    const badge = container.firstElementChild as HTMLElement;
    expect(badge.className).toContain("bg-warning");
    expect(badge.className).toContain("text-warning-foreground");
    expect(badge.textContent).toBe("Pending");
  });
});
