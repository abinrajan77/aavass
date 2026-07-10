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
