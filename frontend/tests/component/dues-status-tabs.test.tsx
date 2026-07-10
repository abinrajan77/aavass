import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { DuesDataTable } from "@/components/billing/dues-data-table";

/**
 * specs/03-maintenance-billing/frontend.md §4.1: "Status Tabs correctly
 * reflect the ?status= query param on direct navigation (deep-linkable
 * filter state)." `next/navigation` is mocked here to simulate landing
 * directly on `.../dues?status=overdue` rather than clicking a tab.
 */
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/towers/tower-a/billing/dues",
  useSearchParams: () => new URLSearchParams("status=overdue"),
}));

const STATUS_OPTIONS = [
  { value: "all", label: "All" },
  { value: "pending", label: "Pending" },
  { value: "overdue", label: "Overdue" },
];

describe("DuesDataTable status tabs", () => {
  it("activates the tab matching the ?status= query param on direct navigation", () => {
    render(
      <DuesDataTable towerId="tower-a" statusOptions={STATUS_OPTIONS} dues={undefined} isLoading={false} />
    );

    const overdueTab = screen.getByRole("tab", { name: "Overdue" });
    const allTab = screen.getByRole("tab", { name: "All" });

    expect(overdueTab).toHaveAttribute("data-state", "active");
    expect(allTab).toHaveAttribute("data-state", "inactive");
  });
});
