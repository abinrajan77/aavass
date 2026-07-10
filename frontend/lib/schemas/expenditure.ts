import { z } from "zod";

// Verbatim from specs/04-special-collections-expenditure/frontend.md
export const MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024; // 10 MB — matches backend presigned policy
export const ACCEPTED_ATTACHMENT_TYPES = ["application/pdf", "image/jpeg", "image/png"];

export const expenditureSchema = z.object({
  expenditure_date: z.date(),
  category: z.enum(["cleaning", "security", "repairs", "utilities", "other"]),
  description: z.string().min(1, "Description is required"),
  vendor_payee_name: z.string().min(1, "Vendor/payee name is required"),
  amount: z.coerce.number().positive("Amount must be greater than 0"),
  payment_mode: z.enum(["cash", "bank_transfer", "cheque"]),
  attachment: z
    .instanceof(File)
    .optional()
    .refine((f) => !f || f.size <= MAX_ATTACHMENT_BYTES, "File must be under 10 MB")
    .refine((f) => !f || ACCEPTED_ATTACHMENT_TYPES.includes(f.type), "Only PDF, JPEG, or PNG files are allowed"),
});

export type ExpenditureInput = z.infer<typeof expenditureSchema>;

export const complexContributionSchema = expenditureSchema.extend({
  complex_total_amount: z.coerce.number().positive().optional(),
  amount: z.coerce.number().positive("Tower's share amount must be greater than 0"),
});

export type ComplexContributionInput = z.infer<typeof complexContributionSchema>;
