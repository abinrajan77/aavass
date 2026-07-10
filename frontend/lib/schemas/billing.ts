import { z } from "zod";
import { startOfToday } from "date-fns";

/**
 * Verbatim from specs/03-maintenance-billing/frontend.md §3 — mirrors the
 * backend Pydantic constraints in backend.md §7 exactly (base_amount/
 * per_sqft_rate `>= 0`, amount_received `> 0`, payment_date can't be future,
 * effective_from can't be past).
 *
 * The "both formula fields zero" refinement is a *soft* warning per
 * overview.md edge case 6 ("technically valid... the system must allow
 * saving... though the frontend should flag it as unusual before submit") —
 * it is surfaced as a confirm step in the UI (see
 * components/billing/formula-form.tsx), never a blocked submit. The zod
 * schema still models it as a `.refine()` with a `message` so the same rule
 * is testable in isolation (see tests/component/formula-form.test.tsx), but
 * the form wires a bypass so the confirm step, not zod, has the final say.
 */
export const MAINTENANCE_FORMULA_ZERO_WARNING =
  "Both Base Amount and Per Sq.Ft. Rate are zero — every due will be ₹0. Confirm this is intentional.";

export const maintenanceFormulaSchema = z
  .object({
    base_amount: z.coerce.number().min(0, "Must be 0 or more"),
    per_sqft_rate: z.coerce.number().min(0, "Must be 0 or more"),
    effective_from: z.coerce.date().refine((d) => d >= startOfToday(), "Cannot be in the past"),
  })
  .refine((d) => d.base_amount > 0 || d.per_sqft_rate > 0, {
    message: MAINTENANCE_FORMULA_ZERO_WARNING,
    path: ["base_amount"],
  }); // soft warning, not a hard block — matches overview.md edge case 6; render as a confirm step, not a blocked submit

export type MaintenanceFormulaInput = z.infer<typeof maintenanceFormulaSchema>;

export const gracePeriodSchema = z.object({
  grace_period_days: z.coerce.number().int().min(0, "Must be 0 or more"),
});

export type GracePeriodInput = z.infer<typeof gracePeriodSchema>;

export const billingCycleSchema = z.object({
  month: z.coerce.number().int().min(1).max(12),
  year: z.coerce.number().int().min(2020).max(2100),
  due_date: z.coerce.date(),
});

export type BillingCycleInput = z.infer<typeof billingCycleSchema>;

export const markPaidSchema = z.object({
  payment_date: z.coerce.date().refine((d) => d <= new Date(), "Cannot be in the future"),
  amount_received: z.coerce.number().gt(0, "Amount received must be greater than 0"),
  payment_mode: z.enum(["cash", "bank_transfer", "cheque"]),
  reference_number: z.string().max(100).optional(),
});

export type MarkPaidInput = z.infer<typeof markPaidSchema>;
