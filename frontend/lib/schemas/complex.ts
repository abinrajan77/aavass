import { z } from "zod";

// Verbatim from specs/01-auth-rbac-tower-setup/frontend.md
export const createComplexSchema = z.object({
  name: z.string().min(2).max(200),
  address: z.string().min(5).max(500),
});

export type CreateComplexInput = z.infer<typeof createComplexSchema>;
