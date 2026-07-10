import { api } from "./client";
import type { Owner } from "./types";

export interface OwnerUpdateInput {
  phone?: string;
  email?: string;
  // Admin-only (MANAGE_RESIDENTS) fields — rejected by the backend's
  // OwnerContactUpdate schema (extra="forbid") for a MANAGE_OWN_FLAT caller,
  // per backend.md's edge case. Never send these from the owner self-service
  // form (lib/schemas/owner.ts's ownerContactUpdateSchema has no such fields
  // to begin with).
  full_name?: string;
  id_number?: string;
}

/**
 * PATCH /api/v1/owners/{owner_id} — global (non-tower-scoped) route since
 * Owner spans towers (backend.md).
 */
export function updateOwner(ownerId: string, input: OwnerUpdateInput) {
  return api.patch<Owner>(`/api/v1/owners/${ownerId}`, input);
}
