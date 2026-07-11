import { api } from "./client";
import type {
  Flat,
  FlatOwnership,
  FlatType,
  OccupancyStatus,
  Paginated,
  Tenant,
  VacateOccupancyStatus,
} from "./types";

export interface FlatFilters {
  page?: number;
  page_size?: number;
  type?: FlatType;
  occupancy_status?: OccupancyStatus;
  /** flat_number search, per backend.md routes table. */
  q?: string;
  // Index signature so this satisfies RequestOptions["params"]'s
  // Record<string, string | number | boolean | undefined> shape.
  [key: string]: string | number | boolean | undefined;
}

export function listFlats(towerId: string, params?: FlatFilters) {
  return api.get<Paginated<Flat>>(`/api/v1/towers/${towerId}/flats`, { params });
}

export function getFlat(towerId: string, flatId: string) {
  return api.get<Flat>(`/api/v1/towers/${towerId}/flats/${flatId}`);
}

export interface FlatCreateInput {
  flat_number: string;
  floor: number;
  type: FlatType;
  carpet_area_sqft: number;
}

export function createFlat(towerId: string, input: FlatCreateInput) {
  return api.post<Flat>(`/api/v1/towers/${towerId}/flats`, input);
}

export function updateFlat(towerId: string, flatId: string, input: Partial<FlatCreateInput>) {
  return api.put<Flat>(`/api/v1/towers/${towerId}/flats/${flatId}`, input);
}

export function deactivateFlat(towerId: string, flatId: string) {
  return api.post<void>(`/api/v1/towers/${towerId}/flats/${flatId}/deactivate`);
}

export function reactivateFlat(towerId: string, flatId: string) {
  return api.post<void>(`/api/v1/towers/${towerId}/flats/${flatId}/reactivate`);
}

// --- Owners (nested under a flat) -----------------------------------------

export function listFlatOwners(towerId: string, flatId: string) {
  return api.get<FlatOwnership[]>(`/api/v1/towers/${towerId}/flats/${flatId}/owners`);
}

/**
 * backend.md: "body OwnerCreate (or {owner_id, date_from, is_primary_contact}
 * to link an existing global Owner)". There is no documented "search owners"
 * endpoint in backend.md's routes table, so linking an existing owner here
 * requires knowing their Owner id up front (see AddOwnerDialog for the UI
 * consequence of this gap).
 */
export type AddFlatOwnerInput =
  | {
      owner_id: string;
      is_primary_contact: boolean;
      date_from: string;
    }
  | {
      full_name: string;
      phone: string;
      email?: string;
      id_number?: string;
      is_primary_contact: boolean;
      date_from: string;
    };

export function addFlatOwner(towerId: string, flatId: string, input: AddFlatOwnerInput) {
  return api.post<FlatOwnership>(`/api/v1/towers/${towerId}/flats/${flatId}/owners`, input);
}

export interface FlatOwnershipUpdateInput {
  is_primary_contact?: boolean;
  new_primary_owner_id?: string;
}

export function updateFlatOwnership(
  towerId: string,
  flatId: string,
  ownershipId: string,
  input: FlatOwnershipUpdateInput
) {
  return api.patch<FlatOwnership>(
    `/api/v1/towers/${towerId}/flats/${flatId}/owners/${ownershipId}`,
    input
  );
}

export interface RemoveFlatOwnershipInput {
  effective_date: string;
  new_primary_owner_id?: string;
}

export function removeFlatOwnership(
  towerId: string,
  flatId: string,
  ownershipId: string,
  input: RemoveFlatOwnershipInput
) {
  return api.post<void>(`/api/v1/towers/${towerId}/flats/${flatId}/owners/${ownershipId}/remove`, input);
}

// --- Tenants (nested under a flat) -----------------------------------------

export function listFlatTenants(towerId: string, flatId: string) {
  return api.get<Tenant[]>(`/api/v1/towers/${towerId}/flats/${flatId}/tenants`);
}

export interface TenantCreateInput {
  full_name: string;
  phone: string;
  email?: string;
  id_number?: string;
  lease_start: string;
  lease_end?: string;
}

export function createFlatTenant(towerId: string, flatId: string, input: TenantCreateInput) {
  return api.post<Tenant>(`/api/v1/towers/${towerId}/flats/${flatId}/tenants`, input);
}

export interface TenantUpdateInput {
  phone?: string;
  email?: string;
  lease_end?: string;
}

export function updateFlatTenant(
  towerId: string,
  flatId: string,
  tenantId: string,
  input: TenantUpdateInput
) {
  return api.patch<Tenant>(`/api/v1/towers/${towerId}/flats/${flatId}/tenants/${tenantId}`, input);
}

export interface TenantVacateInput {
  vacated_date: string;
  occupancy_status: VacateOccupancyStatus;
}

export function vacateFlatTenant(
  towerId: string,
  flatId: string,
  tenantId: string,
  input: TenantVacateInput
) {
  return api.post<Tenant>(`/api/v1/towers/${towerId}/flats/${flatId}/tenants/${tenantId}/vacate`, input);
}

// --- Owner self-service -----------------------------------------------------

/**
 * GET /api/v1/me/flats — cross-tower list of flats the caller currently owns
 * (backend.md). Modeled as a plain array (not the offset-pagination
 * envelope) since it's a personal "my flats" list, not a tower-wide list —
 * backend.md doesn't show a paginated envelope for this specific route.
 */
export function getMyFlats() {
  return api.get<Flat[]>("/api/v1/me/flats");
}

export interface ActiveFlatCount {
  count: number;
}

/**
 * Live per-flat count for the special-collection create dialog's split preview
 * (specs/04-special-collections-expenditure/frontend.md). Module 2's real
 * `GET .../flats` endpoint (see `listFlats` above) doesn't have a dedicated
 * `count_only` mode — this was written against a hypothetical contract before
 * Module 2 landed — so it's derived from the paginated envelope's `total`
 * instead (`page_size: 1`, since only `total` is needed, not the row data).
 * Callers (special-collections-client.tsx) still fall back to the tower's
 * configured `total_flats` with a disclaimer if this errors.
 */
export function getActiveFlatCount(towerId: string): Promise<ActiveFlatCount> {
  return listFlats(towerId, { page: 1, page_size: 1 }).then((result) => ({
    count: result.total,
  }));
}
