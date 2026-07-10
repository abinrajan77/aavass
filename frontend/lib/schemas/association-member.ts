import { z } from "zod";

// Verbatim from specs/01-auth-rbac-tower-setup/frontend.md
export const createAssociationMemberSchema = z.object({
  name: z.string().min(2).max(150),
  email: z.string().email(),
  phone: z.string().regex(/^[6-9]\d{9}$/, "Enter a valid 10-digit Indian mobile number"),
  roleId: z.string().uuid(),
});

export type CreateAssociationMemberInput = z.infer<typeof createAssociationMemberSchema>;
