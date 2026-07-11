import { api } from "./client";
import type { OwnedFlatsResponse, OwnerFlatDashboardResponse } from "./types";

/**
 * Module 5 owner self-service portal endpoints — backend.md §3.
 *
 * NOT Module 2's `GET /api/v1/me/flats` (see `lib/api/flats.ts#getMyFlats`,
 * used only by the root `/` redirect logic). This module's owner-portal
 * frontend (`/my-flats`, `/my-flats/[flatId]/dashboard`) calls these
 * enriched, additively-named endpoints instead, since it needs the
 * due-status badge per flat and the full dashboard aggregate — see
 * backend.md §3.1's "Cross-module read contract" note for why these are
 * deliberately separate endpoints, not a merge.
 */

/** GET /api/v1/owners/me/flats-summary — cross-tower, grouped by tower. */
export function getOwnedFlatsSummary() {
  return api.get<OwnedFlatsResponse>("/api/v1/owners/me/flats-summary");
}

/** GET /api/v1/owners/me/flats/{flat_id}/dashboard — single-flat, single-tower scoped. */
export function getOwnerFlatDashboard(flatId: string) {
  return api.get<OwnerFlatDashboardResponse>(`/api/v1/owners/me/flats/${flatId}/dashboard`);
}
