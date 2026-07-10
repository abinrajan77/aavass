import { z } from "zod";

// Verbatim from specs/01-auth-rbac-tower-setup/frontend.md
export const createTowerSchema = z.object({
  name: z.string().min(1).max(100),
  code: z.string().regex(/^[A-Z0-9]{2,10}$/, "2-10 uppercase letters/digits"), // used in receipt numbering by Module 3
  totalFloors: z.number().int().positive(),
  totalFlats: z.number().int().positive(),
  associationName: z.string().min(1).max(200),
});

export type CreateTowerInput = z.infer<typeof createTowerSchema>;
