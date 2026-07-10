import { z } from "zod";

// Verbatim from specs/04-special-collections-expenditure/frontend.md
export const specialCollectionSchema = z.object({
  title: z.string().min(1, "Title is required").max(200),
  description: z.string().optional(),
  total_amount: z.coerce.number().positive("Total amount must be greater than 0"),
  split_basis: z.literal("equal"),
  due_date: z.date().refine((d) => d > new Date(), "Due date must be in the future"),
});

export type SpecialCollectionInput = z.infer<typeof specialCollectionSchema>;

/**
 * Verbatim from specs/04-special-collections-expenditure/frontend.md.
 *
 * NOT wired to a component in this slice — the mark-paid dialog is out of
 * scope (its backend endpoint delegates to Module 3's `record_payment()`,
 * and Module 3 doesn't exist in this repo yet; see this module's kickoff
 * constraints). Kept here so the validated shape is ready to wire up as soon
 * as Module 3 lands and the backend's `POST .../dues/{due_id}/mark-paid`
 * becomes callable.
 */
export const markPaidSchema = z.object({
  payment_date: z.date(),
  amount_received: z.coerce.number().positive(),
  payment_mode: z.enum(["cash", "bank_transfer", "cheque"]),
  reference_number: z.string().optional(),
});

export type MarkPaidInput = z.infer<typeof markPaidSchema>;
