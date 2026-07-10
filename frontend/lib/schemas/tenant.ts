import { z } from "zod";

// Mirrors specs/02-flat-owner-tenant/backend.md `TenantCreate` 1:1,
// including the `lease_end >= lease_start` model_validator so this fails
// client-side with the same shape of error the server would return
// (frontend.md: "so client-side validation errors match server-side ones").
export const tenantCreateSchema = z
  .object({
    full_name: z.string().min(2, "Full name is required").max(150),
    phone: z.string().regex(/^[6-9]\d{9}$/, "Enter a valid 10-digit Indian mobile number"),
    email: z.union([z.string().email("Enter a valid email"), z.literal("")]).optional(),
    id_number: z.string().max(50).optional(),
    lease_start: z.string().min(1, "Lease start date is required"),
    lease_end: z.string().optional(),
  })
  .refine((data) => !data.lease_end || data.lease_end >= data.lease_start, {
    message: "lease_end must not be before lease_start",
    path: ["lease_end"],
  });
export type TenantCreate = z.infer<typeof tenantCreateSchema>;

// Corrections to an already-active tenant (backend.md PATCH .../tenants/{id}
// — "does not touch is_active").
export const tenantUpdateSchema = z.object({
  phone: z.string().regex(/^[6-9]\d{9}$/, "Enter a valid 10-digit Indian mobile number").optional(),
  email: z.union([z.string().email("Enter a valid email"), z.literal("")]).optional(),
  lease_end: z.string().optional(),
});
export type TenantUpdate = z.infer<typeof tenantUpdateSchema>;

// Mirrors `TenantVacate` 1:1 — `occupancy_status` has NO default and is
// restricted to owner_occupied/vacant (never tenant_occupied), per
// overview.md's "Marking a tenant vacated without specifying the new
// occupancy status" edge case. Leaving it `undefined` until the admin/owner
// makes an explicit choice is what keeps the dialog's submit button disabled
// (frontend.md test plan).
export const VACATE_OCCUPANCY_STATUSES = ["owner_occupied", "vacant"] as const;

export const tenantVacateSchema = z.object({
  vacated_date: z.string().min(1, "Vacated date is required"),
  occupancy_status: z.enum(VACATE_OCCUPANCY_STATUSES, {
    message: "Select the resulting occupancy status",
  }),
});
export type TenantVacate = z.infer<typeof tenantVacateSchema>;
