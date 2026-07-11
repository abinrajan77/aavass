import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { ReportStatusBadge } from "@/components/reports/report-status-badge";

/**
 * specs/05-reporting-owner-portal-notifications/frontend.md "Frontend Test
 * Plan": "report `DataTable` renders the shared status `Badge` variants
 * (success/warning/destructive) matching the exact tokens from
 * 00-architecture-and-standards.md §3.1 — regression test against a
 * hard-coded color swatch to catch drift from ad-hoc colors." Every report
 * tab (and the owner dashboard) renders a report row's status through this
 * shared `ReportStatusBadge`, so testing it directly covers all of them.
 */
describe("ReportStatusBadge", () => {
  it("renders the success token for a paid row", () => {
    const { container } = render(<ReportStatusBadge status="paid" />);
    expect(container.querySelector(".bg-success")).not.toBeNull();
    expect(container.querySelector(".bg-warning")).toBeNull();
    expect(container.querySelector(".bg-destructive")).toBeNull();
  });

  it("renders the warning token for a pending row", () => {
    const { container } = render(<ReportStatusBadge status="pending" />);
    expect(container.querySelector(".bg-warning")).not.toBeNull();
    expect(container.querySelector(".bg-success")).toBeNull();
    expect(container.querySelector(".bg-destructive")).toBeNull();
  });

  it("renders the destructive token for an overdue row", () => {
    const { container } = render(<ReportStatusBadge status="overdue" />);
    expect(container.querySelector(".bg-destructive")).not.toBeNull();
    expect(container.querySelector(".bg-success")).toBeNull();
    expect(container.querySelector(".bg-warning")).toBeNull();
  });
});
