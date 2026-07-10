import { z } from "zod";

// Verbatim from specs/01-auth-rbac-tower-setup/frontend.md
export const createRoleSchema = z.object({
  name: z.string().min(2).max(80),
  permissionCodes: z.array(z.string()).min(1, "Select at least one permission"),
});

export type CreateRoleInput = z.infer<typeof createRoleSchema>;
