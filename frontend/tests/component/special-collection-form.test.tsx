import { describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "./test-utils";
import { SpecialCollectionForm } from "@/app/(app)/towers/[towerId]/special-collections/special-collection-form";
import { specialCollectionSchema } from "@/lib/schemas/special-collection";

describe("specialCollectionSchema", () => {
  /**
   * frontend.md Component test #2: "Due-date-in-future validation on
   * special collection form." Exercised directly against the zod schema
   * (rather than by clicking a calendar day) because the form's
   * `DatePickerField` disables past/today dates in the UI itself
   * (defense-in-depth — see the "past dates are disabled in the picker"
   * test below), so there is no way to *click* a past date through the
   * rendered calendar to trigger the error path.
   */
  it("rejects a due_date in the past with the expected message", () => {
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);

    const result = specialCollectionSchema.safeParse({
      title: "Lift Modernization Fund",
      total_amount: 100000,
      split_basis: "equal",
      due_date: yesterday,
    });

    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues.some((i) => i.message === "Due date must be in the future")).toBe(true);
    }
  });

  it("accepts a due_date in the future", () => {
    const nextMonth = new Date();
    nextMonth.setMonth(nextMonth.getMonth() + 1);

    const result = specialCollectionSchema.safeParse({
      title: "Lift Modernization Fund",
      total_amount: 100000,
      split_basis: "equal",
      due_date: nextMonth,
    });

    expect(result.success).toBe(true);
  });
});

describe("SpecialCollectionForm", () => {
  it("disables past and today's dates in the due-date picker so one can't be selected", async () => {
    const user = userEvent.setup();
    renderWithProviders(<SpecialCollectionForm activeFlatCount={20} onSubmit={vi.fn()} />);

    // The trigger button's accessible name comes from its associated
    // <FormLabel> ("Due date"), which the accessible-name algorithm prefers
    // over the button's own "Pick a date" text content.
    await user.click(screen.getByRole("button", { name: /due date/i }));

    // Day buttons get an aria-label of the full formatted date (react-day-picker's
    // default `labelDayButton`), not just the day number, so locate by the
    // `data-day` attribute CalendarDayButton sets instead of accessible name.
    const today = new Date();
    const todayButton = document.querySelector(`button[data-day="${today.toLocaleDateString()}"]`);
    expect(todayButton).not.toBeNull();
    expect(todayButton).toBeDisabled();
  });

  it("shows the live per-flat split preview reactively as total_amount changes", async () => {
    const user = userEvent.setup();
    renderWithProviders(<SpecialCollectionForm activeFlatCount={20} onSubmit={vi.fn()} />);

    await user.type(screen.getByLabelText(/total amount/i), "100000");

    await waitFor(
      () => {
        expect(screen.getByTestId("split-preview")).toHaveTextContent(/₹5,000\.00 per flat across 20 flats/);
      },
      { timeout: 1000 }
    );
  });

  it("does not call onSubmit when required fields are missing", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    renderWithProviders(<SpecialCollectionForm activeFlatCount={20} onSubmit={onSubmit} />);

    await user.click(screen.getByRole("button", { name: /create special collection/i }));

    await waitFor(() => {
      expect(onSubmit).not.toHaveBeenCalled();
    });
  });
});
