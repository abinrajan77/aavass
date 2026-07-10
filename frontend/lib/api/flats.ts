import { api } from "./client";

export interface ActiveFlatCount {
  count: number;
}

/**
 * Module 2 (Flat/Owner/Tenant Management) is not built in this repo yet —
 * per specs/00-architecture-and-standards.md §2, Module 2 must land before
 * Modules 3/4 in dependency order, but this frontend slice is being built in
 * parallel per the workshop's schedule. This is typed against the contract
 * frontend.md calls out for the special-collection create dialog's live
 * per-flat split preview: "fetched via a lightweight
 * `GET .../flats?status=active&count_only=true` or reused from Module 2's
 * active-flat count."
 *
 * Until Module 2 ships this 404s in dev; callers (see
 * special-collections-client.tsx) fall back to the tower's configured
 * `total_flats` with a disclaimer rather than blocking the dialog.
 */
export function getActiveFlatCount(towerId: string) {
  return api.get<ActiveFlatCount>(`/api/v1/towers/${towerId}/flats`, {
    params: { status: "active", count_only: true },
  });
}
