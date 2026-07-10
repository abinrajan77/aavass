import { z } from "zod";

// Mirrors specs/02-flat-owner-tenant/backend.md `OwnerCreate` 1:1. Used for
// the "Add Co-owner" dialog's "create a new global Owner" path
// (frontend.md: "search existing global Owner by phone/email or create
// new").
export const ownerCreateSchema = z.object({
  full_name: z.string().min(2, "Full name is required").max(150),
  phone: z.string().regex(/^[6-9]\d{9}$/, "Enter a valid 10-digit Indian mobile number"),
  email: z.union([z.string().email("Enter a valid email"), z.literal("")]).optional(),
  id_number: z.string().max(50).optional(),
  is_primary_contact: z.boolean(),
  date_from: z.string().min(1, "Date is required"),
});
export type OwnerCreate = z.infer<typeof ownerCreateSchema>;

// backend.md: `model_config = ConfigDict(extra="forbid")` — the ONLY fields
// MANAGE_OWN_FLAT may write; full_name/id_number require MANAGE_RESIDENTS.
// This schema intentionally has no full_name/id_number field at all so the
// owner self-service form can never render/submit them even by accident
// (frontend.md "What must NOT break": identity fields must never render as
// editable inputs in the owner self-service view).
export const ownerContactUpdateSchema = z.object({
  phone: z.string().regex(/^[6-9]\d{9}$/, "Enter a valid 10-digit Indian mobile number").optional(),
  email: z.union([z.string().email("Enter a valid email"), z.literal("")]).optional(),
});
export type OwnerContactUpdate = z.infer<typeof ownerContactUpdateSchema>;

// Admin-only variant of the same PATCH /api/v1/owners/{owner_id} route —
// MANAGE_RESIDENTS callers may additionally change full_name/id_number
// (backend.md "Owner updating their own contact details vs. admin doing it").
export const ownerAdminUpdateSchema = ownerContactUpdateSchema.extend({
  full_name: z.string().min(2, "Full name is required").max(150).optional(),
  id_number: z.string().max(50).optional(),
});
export type OwnerAdminUpdate = z.infer<typeof ownerAdminUpdateSchema>;

// Mirrors `FlatOwnershipUpdate` 1:1.
export const flatOwnershipUpdateSchema = z.object({
  is_primary_contact: z.boolean().optional(),
  new_primary_owner_id: z.string().uuid().optional(),
});
export type FlatOwnershipUpdate = z.infer<typeof flatOwnershipUpdateSchema>;
