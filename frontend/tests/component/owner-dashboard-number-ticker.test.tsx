import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { FlatDashboardClient } from "@/app/(app)/my-flats/[flatId]/dashboard/dashboard-client";
import type { OwnerFlatDashboardResponse } from "@/lib/api/types";

/**
 * specs/05-reporting-owner-portal-notifications/frontend.md "Frontend Test
 * Plan": "owner dashboard's `NumberTicker` cells render the correct final
 * value (post-animation) matching `ytd_totals` from a mocked API response."
 */
const DASHBOARD_RESPONSE: OwnerFlatDashboardResponse = {
  flat_id: "flat-1",
  tower_id: "tower-a",
  flat_number: "A-101",
  current_due: null,
  payment_history: [],
  receipts: [],
  tower_expenditures: [],
  tenant_history: [],
  ytd_totals: { total_due_ytd: 30000, total_paid_ytd: 24000 },
};

function renderDashboard() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <FlatDashboardClient flatId="flat-1" />
    </QueryClientProvider>
  );
}

describe("FlatDashboardClient NumberTicker cells", () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;

  afterEach(() => {
    fetchSpy?.mockRestore();
  });

  it("renders the correct post-animation YTD values from the mocked dashboard response", async () => {
    fetchSpy = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify(DASHBOARD_RESPONSE), {
        status: 200,
        headers: { "content-type": "application/json" },
      })
    );

    renderDashboard();

    expect(await screen.findByText("Flat A-101")).toBeInTheDocument();

    expect(await screen.findByText("₹24,000.00", {}, { timeout: 3000 })).toBeInTheDocument();
    expect(await screen.findByText("₹30,000.00", {}, { timeout: 3000 })).toBeInTheDocument();
    expect(screen.queryByText("₹NaN")).not.toBeInTheDocument();
  });
});
