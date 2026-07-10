import { describe, expect, it } from "vitest";
import { addDays, subDays } from "date-fns";
import {
  MAINTENANCE_FORMULA_ZERO_WARNING,
  billingCycleSchema,
  gracePeriodSchema,
  maintenanceFormulaSchema,
  markPaidSchema,
} from "@/lib/schemas/billing";

/**
 * Unit-level coverage of the zod schemas from
 * specs/03-maintenance-billing/frontend.md §3, which are meant to mirror
 * the backend Pydantic constraints in backend.md §7 exactly. Testing the
 * schemas directly (in addition to the component-level dialog tests) pins
 * down the exact boundary behavior — e.g. the `payment_date` "not in the
 * future" rule — independent of how any particular form wires the date
 * picker UI.
 */
describe("markPaidSchema", () => {
  const base = { payment_date: new Date(), amount_received: 100, payment_mode: "cash" as const };

  it("rejects amount_received = 0", () => {
    const result = markPaidSchema.safeParse({ ...base, amount_received: 0 });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues.some((i) => i.path.includes("amount_received"))).toBe(true);
    }
  });

  it("rejects a negative amount_received", () => {
    const result = markPaidSchema.safeParse({ ...base, amount_received: -50 });
    expect(result.success).toBe(false);
  });

  it("accepts an amount_received just above 0", () => {
    const result = markPaidSchema.safeParse({ ...base, amount_received: 0.01 });
    expect(result.success).toBe(true);
  });

  it("rejects a payment_date in the future", () => {
    const result = markPaidSchema.safeParse({ ...base, payment_date: addDays(new Date(), 1) });
    expect(result.success).toBe(false);
  });

  it("accepts today as payment_date", () => {
    const result = markPaidSchema.safeParse({ ...base, payment_date: new Date() });
    expect(result.success).toBe(true);
  });
});

describe("maintenanceFormulaSchema", () => {
  it("rejects a negative base_amount", () => {
    const result = maintenanceFormulaSchema.safeParse({
      base_amount: -1,
      per_sqft_rate: 2,
      effective_from: new Date(),
    });
    expect(result.success).toBe(false);
  });

  it("rejects an effective_from in the past", () => {
    const result = maintenanceFormulaSchema.safeParse({
      base_amount: 1000,
      per_sqft_rate: 2,
      effective_from: subDays(new Date(), 1),
    });
    expect(result.success).toBe(false);
  });

  it("flags base_amount = 0 and per_sqft_rate = 0 with the soft-warning message, not a generic error", () => {
    const result = maintenanceFormulaSchema.safeParse({
      base_amount: 0,
      per_sqft_rate: 0,
      effective_from: new Date(),
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues).toHaveLength(1);
      expect(result.error.issues[0].message).toBe(MAINTENANCE_FORMULA_ZERO_WARNING);
    }
  });

  it("accepts base_amount = 0 as long as per_sqft_rate > 0 (each component independently zeroable)", () => {
    const result = maintenanceFormulaSchema.safeParse({
      base_amount: 0,
      per_sqft_rate: 2,
      effective_from: new Date(),
    });
    expect(result.success).toBe(true);
  });
});

describe("gracePeriodSchema", () => {
  it("rejects a negative grace_period_days", () => {
    expect(gracePeriodSchema.safeParse({ grace_period_days: -1 }).success).toBe(false);
  });

  it("accepts 0 (edge case 2 — 0 is valid, just surfaced with helper text in the UI)", () => {
    expect(gracePeriodSchema.safeParse({ grace_period_days: 0 }).success).toBe(true);
  });
});

describe("billingCycleSchema", () => {
  it("rejects month outside 1-12", () => {
    expect(
      billingCycleSchema.safeParse({ month: 13, year: 2026, due_date: new Date() }).success
    ).toBe(false);
    expect(
      billingCycleSchema.safeParse({ month: 0, year: 2026, due_date: new Date() }).success
    ).toBe(false);
  });

  it("accepts a valid month/year/due_date", () => {
    expect(
      billingCycleSchema.safeParse({ month: 7, year: 2026, due_date: new Date() }).success
    ).toBe(true);
  });
});
