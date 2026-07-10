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
