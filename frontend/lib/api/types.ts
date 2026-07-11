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

/**
 * Module 3 (Maintenance Billing) shapes, mirrored from
 * specs/03-maintenance-billing/backend.md §6-§7. The backend is being built
 * concurrently to this same spec by another agent — these types describe the
 * agreed contract, not something inspected from a live backend.
 */
export interface MaintenanceFormula {
  id: string;
  tower_id: string;
  base_amount: number;
  per_sqft_rate: number;
  effective_from: string;
  created_by: string;
  created_by_name?: string;
  created_at: string;
}

export interface GracePeriodConfig {
  id: string;
  tower_id: string;
  grace_period_days: number;
  effective_from: string;
  created_by: string;
  created_by_name?: string;
  created_at: string;
}

export type BillingCycleStatus = "generating" | "active";

export interface BillingCycle {
  id: string;
  tower_id: string;
  month: number;
  year: number;
  due_date: string;
  status: BillingCycleStatus;
  formula_id: string;
  grace_period_days_snapshot: number;
  total_dues: number;
  total_collected: number;
  pending_count: number;
  overdue_count: number;
}

/** Embedded snapshot returned alongside a single cycle's detail fetch. */
export interface BillingCycleDetail extends BillingCycle {
  formula_snapshot?: Pick<MaintenanceFormula, "base_amount" | "per_sqft_rate" | "effective_from">;
}

/** `202` response body for the async (>300 flats) billing-cycle generation path. */
export interface BillingCycleJobAccepted {
  cycle_id: string;
  job_id: string;
  status: "generating";
}

export type DueAssignedToType = "tenant" | "owner";
export type MaintenanceDueStatus = "pending" | "paid" | "overdue";

export interface MaintenanceDue {
  id: string;
  flat_id: string;
  flat_number: string;
  amount: number;
  assigned_to_type: DueAssignedToType;
  assigned_to_name_snapshot: string;
  due_date: string;
  status: MaintenanceDueStatus;
}

export interface BillingDashboardStats {
  total_collected_this_cycle: number;
  pending_count: number;
  overdue_amount: number;
}

export type PaymentMode = "cash" | "bank_transfer" | "cheque";

export interface ReceiptOut {
  id: string;
  receipt_number: string;
  owner_name_snapshot: string;
  generated_at: string;
  download_url: string;
}

export interface MarkPaidResponse {
  due: MaintenanceDue;
  receipt: ReceiptOut;
}

/** Shared canonical async-job status route — 06-cloud-devops.md §4. */
export type JobStatus = "pending" | "in_progress" | "done" | "failed";

export interface JobStatusResponse {
  job_id: string;
  status: JobStatus;
  error?: string | null;
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
// PaymentMode is already declared above (Module 3) — cash/bank_transfer/cheque covers both
// maintenance payments and expenditure records identically.

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
