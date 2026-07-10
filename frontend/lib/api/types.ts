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

/**
 * Module 4 — Special Collections & Expenditure. Mirrored from
 * specs/04-special-collections-expenditure/backend.md "Pydantic schemas
 * (representative)" — the backend for this module is being built
 * concurrently by another agent (scoped to exclude the mark-paid/receipt
 * flow, which hard-depends on Module 3 — not yet built in this repo). Treat
 * these as the agreed contract, not something inspected from a live backend.
 */
export type SplitBasis = "equal";

export interface SkippedFlat {
  flat_id: string;
  flat_number: string;
  reason: "NO_ACTIVE_OWNER";
}

export interface SpecialCollection {
  id: string;
  tower_id: string;
  title: string;
  description: string | null;
  total_amount: number;
  split_basis: SplitBasis;
  due_date: string;
  dues_generated_at: string | null;
  skipped_flats: SkippedFlat[];
  collected_amount: number;
  pending_count: number;
  paid_count: number;
  overdue_count: number;
  created_at: string;
}

/**
 * `POST .../special-collections` response shape — synchronous (<=300 active
 * flats, 201) includes the full collection; the async path (>300 flats, 202)
 * returns only a job id to poll, per backend.md's latency-budget note.
 */
export type CreateSpecialCollectionResponse =
  | (SpecialCollection & { dues_generated: true })
  | { job_id: string; dues_generated: false; skipped_flats: SkippedFlat[] };

export type DueStatus = "pending" | "paid" | "overdue";

export interface SpecialCollectionDue {
  id: string;
  special_collection_id: string;
  flat_id: string;
  flat_number: string;
  owner_id: string;
  owner_name: string;
  amount: number;
  due_date: string;
  status: DueStatus;
}

export type ExpenditureCategory = "cleaning" | "security" | "repairs" | "utilities" | "other";
export type PaymentMode = "cash" | "bank_transfer" | "cheque";

export interface Expenditure {
  id: string;
  tower_id: string;
  expenditure_date: string;
  category: ExpenditureCategory;
  description: string;
  vendor_payee_name: string;
  amount: number;
  payment_mode: PaymentMode;
  attachment_s3_key: string | null;
  is_complex_contribution: boolean;
  complex_total_amount: number | null;
  recorded_by: string;
  created_at: string;
  updated_at: string;
  deactivated_at: string | null;
}

export interface AttachmentUploadUrlResponse {
  upload_url: string;
  attachment_s3_key: string;
}

export interface AttachmentUrlResponse {
  url: string;
}
