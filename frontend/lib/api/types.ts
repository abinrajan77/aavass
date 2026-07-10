/**
 * Shared API shapes, mirrored from specs/01-auth-rbac-tower-setup/backend.md.
 * The backend is being built concurrently to this same spec by another agent
 * — these types describe the agreed contract, not something inspected from a
 * live backend.
 */

export type AccountType = "superuser" | "tower_admin" | "flat_owner";

export interface SessionUser {
  id: string;
  email: string;
  account_type: AccountType;
  is_superuser: boolean;
  name?: string;
}

export interface SessionTower {
  tower_id: string;
  tower_name: string;
  role_name: string;
}

/** Shape returned by POST /api/v1/auth/login and used for our own readable session cookie. */
export interface LoginResponse {
  user: SessionUser;
  permissions: string[];
  towers: SessionTower[];
}

export interface ApartmentComplex {
  id: string;
  name: string;
  address: string;
  deactivated_at: string | null;
  created_at: string;
}

export interface Tower {
  id: string;
  complex_id: string;
  name: string;
  code: string;
  total_floors: number;
  total_flats: number;
  association_name: string;
  deactivated_at: string | null;
  created_at: string;
}

export interface Role {
  id: string;
  tower_id: string;
  name: string;
  is_system_default: boolean;
  permission_codes: string[];
  deactivated_at: string | null;
}

export interface AssociationMember {
  id: string;
  tower_id: string;
  user_id: string;
  name: string;
  email: string;
  phone: string;
  role_id: string;
  role_name: string;
  deactivated_at: string | null;
  created_at: string;
}

export interface CreateAssociationMemberResponse {
  member: AssociationMember;
  temporary_password: string;
}

/**
 * Module 2 (specs/02-flat-owner-tenant) shapes — mirrored 1:1 from
 * backend.md's Pydantic schemas/SQLAlchemy tables. The backend is being
 * built concurrently to the same spec by another agent.
 */
export type FlatType = "1BHK" | "2BHK" | "3BHK" | "OTHER";
export type OccupancyStatus = "owner_occupied" | "tenant_occupied" | "vacant";
/** Enum accepted by TenantVacate.occupancy_status — never "tenant_occupied" (backend.md). */
export type VacateOccupancyStatus = Extract<OccupancyStatus, "owner_occupied" | "vacant">;

export interface OwnerSummary {
  id: string;
  full_name: string;
  phone: string;
  email: string | null;
}

export interface TenantSummary {
  id: string;
  full_name: string;
  phone: string;
  email: string | null;
}

export interface Flat {
  id: string;
  tower_id: string;
  flat_number: string;
  floor: number;
  type: FlatType;
  carpet_area_sqft: number;
  occupancy_status: OccupancyStatus;
  primary_owner: OwnerSummary | null;
  active_tenant: TenantSummary | null;
  deactivated_at: string | null;
}

export interface Owner {
  id: string;
  /** FK to users.id — nullable until the owner registers a login. Used on
   * the frontend only to match "which co-owner is the logged-in user" on
   * /my-flats/[flatId] (backend.md doesn't spell this out explicitly, but
   * it's a real column on the Owner table). */
  user_id: string | null;
  full_name: string;
  phone: string;
  email: string | null;
  id_number: string | null;
  created_at: string;
  deactivated_at: string | null;
}

/**
 * Response shape for GET/POST/PATCH .../flats/{flat_id}/owners. backend.md's
 * routes table doesn't spell out a dedicated "FlatOwnershipOut" schema, but
 * frontend.md requires the Owners tab to show name/phone/email per row, so
 * this assumes the nested `owner` is joined in the response — flag to the
 * backend agent if it's returned as separate owner_id-only rows instead.
 */
export interface FlatOwnership {
  id: string;
  flat_id: string;
  owner_id: string;
  /** Full Owner (not just OwnerSummary) so /my-flats/[flatId] can match
   * `owner.user_id === session.user.id` to find "my own" contact record. */
  owner: Owner;
  is_primary_contact: boolean;
  date_from: string;
  date_to: string | null;
  created_at: string;
}

export interface Tenant {
  id: string;
  flat_id: string;
  full_name: string;
  phone: string;
  email: string | null;
  id_number: string | null;
  lease_start: string;
  lease_end: string | null;
  is_active: boolean;
  vacated_at: string | null;
  created_at: string;
}

/** RFC7807-style error envelope — specs/00-architecture-and-standards.md §6. */
export interface ProblemDetails {
  error_code: string;
  message: string;
  field_errors: Record<string, string[]> | null;
}

/** Offset-pagination envelope — specs/00-architecture-and-standards.md §6. */
export interface Paginated<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}
