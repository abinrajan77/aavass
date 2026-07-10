import { z } from "zod";

// Mirrors specs/02-flat-owner-tenant/backend.md `FlatCreate`/`FlatUpdate`
// Pydantic schemas 1:1 (field names/enum values match exactly) so
// client-side validation errors line up with server-side ones — per
// frontend.md "Data fetching / validation".
export const FLAT_TYPES = ["1BHK", "2BHK", "3BHK", "OTHER"] as const;

export const flatCreateSchema = z.object({
  flat_number: z.string().min(1, "Flat number is required").max(20),
  floor: z.number().int("Floor must be a whole number"),
  type: z.enum(FLAT_TYPES),
  carpet_area_sqft: z.number().positive("Carpet area must be greater than 0"),
});
export type FlatCreate = z.infer<typeof flatCreateSchema>;

// FlatUpdate: same fields, all optional. occupancy_status is deliberately
// absent — backend.md: "occupancy_status is NEVER directly settable via this
// schema — only via tenant add/vacate transitions".
export const flatUpdateSchema = z.object({
  flat_number: z.string().min(1, "Flat number is required").max(20).optional(),
  floor: z.number().int("Floor must be a whole number").optional(),
  type: z.enum(FLAT_TYPES).optional(),
  carpet_area_sqft: z.number().positive("Carpet area must be greater than 0").optional(),
});
export type FlatUpdate = z.infer<typeof flatUpdateSchema>;
