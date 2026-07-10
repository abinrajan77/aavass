import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FormulaForm } from "@/components/billing/formula-form";

/**
 * specs/03-maintenance-billing/frontend.md §4.1: "Formula Form shows the
 * 'both zero' soft-warning confirm step when base_amount = 0 and
 * per_sqft_rate = 0, but still allows submit after confirmation" — per
 * overview.md edge case 6, this must be a confirmable warning, not a
 * blocked submit.
 */
describe("FormulaForm", () => {
  it("shows a confirm step (not a blocked submit) when both fields are zero, and calls onSubmit after confirming", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<FormulaForm onSubmit={onSubmit} defaultValues={{ base_amount: 0, per_sqft_rate: 0 }} />);

    await user.click(screen.getByRole("button", { name: /save formula/i }));

    // Confirm step (Dialog) appears; onSubmit has not fired yet. Scoped to
    // the dialog's heading specifically — the same warning text also
    // appears in the inline FormMessage under the field, which is the
    // point (the confirm step surfaces the same rule, it doesn't replace it).
    expect(await screen.findByRole("heading", { name: /every due will be ₹0/i })).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: /confirm and save/i }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit.mock.calls[0][0]).toMatchObject({ base_amount: 0, per_sqft_rate: 0 });
  });

  it("submits directly, with no confirm step, when the fields are not both zero", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<FormulaForm onSubmit={onSubmit} defaultValues={{ base_amount: 1000, per_sqft_rate: 2 }} />);

    await user.click(screen.getByRole("button", { name: /save formula/i }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(screen.queryByText(/every due will be ₹0/i)).not.toBeInTheDocument();
  });

  it("renders a live preview that recomputes from base_amount + carpet_area × per_sqft_rate", async () => {
    const user = userEvent.setup();
    render(
      <FormulaForm onSubmit={vi.fn()} defaultValues={{ base_amount: 1000, per_sqft_rate: 2 }} sampleCarpetAreas={[600]} />
    );

    // 1000 + 600*2 = 2200.00
    expect(await screen.findByText("₹2,200.00")).toBeInTheDocument();

    const rateInput = screen.getByLabelText(/per sq\.ft\. rate/i);
    await user.clear(rateInput);
    await user.type(rateInput, "3");

    // 1000 + 600*3 = 2800.00
    expect(await screen.findByText("₹2,800.00")).toBeInTheDocument();
  });
});
