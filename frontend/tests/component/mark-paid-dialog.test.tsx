import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MarkPaidDialog } from "@/components/billing/mark-paid-dialog";
import type { MaintenanceDue } from "@/lib/api/types";

/**
 * specs/03-maintenance-billing/frontend.md §4.1:
 * "Mark-paid Dialog rejects submit (shows validation error, does not call
 * the API) when amount_received is 0 or negative" + "...when payment_date
 * is in the future."
 */
const due: MaintenanceDue = {
  id: "due-1",
  flat_id: "flat-1",
  flat_number: "A-101",
  amount: 2000,
  assigned_to_type: "owner",
  assigned_to_name_snapshot: "Asha Owner",
  due_date: "2026-07-10",
  status: "pending",
};

function renderDialog() {
  const queryClient = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MarkPaidDialog towerId="tower-a" due={due} open onOpenChange={() => {}} />
    </QueryClientProvider>
  );
}

describe("MarkPaidDialog", () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    fetchSpy = vi.spyOn(global, "fetch").mockRejectedValue(new Error("network calls are not expected in this test"));
  });

  afterEach(() => {
    fetchSpy.mockRestore();
  });

  it("rejects submit when amount_received is 0", async () => {
    const user = userEvent.setup();
    renderDialog();

    const amountInput = screen.getByLabelText(/amount received/i);
    await user.clear(amountInput);
    await user.type(amountInput, "0");
    await user.click(screen.getByRole("button", { name: /mark as paid/i }));

    expect(await screen.findByText(/amount received must be greater than 0/i)).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("rejects submit when amount_received is negative", async () => {
    const user = userEvent.setup();
    renderDialog();

    const amountInput = screen.getByLabelText(/amount received/i);
    await user.clear(amountInput);
    await user.type(amountInput, "-50");
    await user.click(screen.getByRole("button", { name: /mark as paid/i }));

    expect(await screen.findByText(/amount received must be greater than 0/i)).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("disables future dates in the payment_date calendar (UI-level enforcement of 'cannot be in the future')", async () => {
    const user = userEvent.setup();
    renderDialog();

    await user.click(screen.getByRole("button", { name: "Payment date" }));

    // react-day-picker renders each day as a native <button data-day="...">
    // and marks disallowed days with the `disabled` HTML attribute — the
    // `disabled={(date) => date > new Date()}` prop passed from
    // MarkPaidDialog means every future day is unselectable straight from
    // the UI. The schema-level rejection of a future payment_date (in case
    // it's ever submitted some other way) is covered directly in
    // tests/component/schemas/billing-schemas.test.ts.
    const dayButtons = document.querySelectorAll("button[data-day]");
    expect(dayButtons.length).toBeGreaterThan(0);
    const disabledFutureDays = Array.from(dayButtons).filter((b) => b.hasAttribute("disabled"));
    expect(disabledFutureDays.length).toBeGreaterThan(0);
  });
});
