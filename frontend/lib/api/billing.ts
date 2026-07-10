import { api, apiFetchWithStatus, type ResponseWithStatus } from "./client";
import type {
  BillingCycle,
  BillingCycleDetail,
  BillingCycleJobAccepted,
  BillingDashboardStats,
  GracePeriodConfig,
  MaintenanceDue,
  MaintenanceDueStatus,
  MaintenanceFormula,
  MarkPaidResponse,
  Paginated,
  PaymentMode,
} from "./types";

/**
 * Module 3 (Maintenance Billing) API client — mirrors
 * specs/03-maintenance-billing/backend.md §6 route-by-route. Tower-scoped
 * throughout, per specs/00-architecture-and-standards.md §6 ("no top-level
 * /api/v1/dues/... routes — every module's resources nest under
 * /api/v1/towers/{tower_id}/...").
 */

// --- 6.1 Maintenance formula --------------------------------------------

export function listMaintenanceFormulas(towerId: string, params?: { page?: number; page_size?: number }) {
  return api.get<Paginated<MaintenanceFormula>>(`/api/v1/towers/${towerId}/maintenance-formula`, { params });
}

export function getCurrentMaintenanceFormula(towerId: string) {
  return api.get<MaintenanceFormula>(`/api/v1/towers/${towerId}/maintenance-formula/current`);
}

export function createMaintenanceFormula(
  towerId: string,
  input: { base_amount: number; per_sqft_rate: number; effective_from?: string }
) {
  return api.post<MaintenanceFormula>(`/api/v1/towers/${towerId}/maintenance-formula`, input);
}

// --- 6.2 Grace period ----------------------------------------------------

export function getCurrentGracePeriodConfig(towerId: string) {
  return api.get<GracePeriodConfig>(`/api/v1/towers/${towerId}/grace-period-config/current`);
}

export function listGracePeriodConfigs(towerId: string, params?: { page?: number; page_size?: number }) {
  return api.get<Paginated<GracePeriodConfig>>(`/api/v1/towers/${towerId}/grace-period-config`, { params });
}

export function createGracePeriodConfig(towerId: string, input: { grace_period_days: number }) {
  return api.post<GracePeriodConfig>(`/api/v1/towers/${towerId}/grace-period-config`, input);
}

// --- 6.3 Billing cycles ---------------------------------------------------

export function listBillingCycles(towerId: string, params?: { page?: number; page_size?: number }) {
  return api.get<Paginated<BillingCycle>>(`/api/v1/towers/${towerId}/billing-cycles`, { params });
}

export function getBillingCycle(towerId: string, cycleId: string) {
  return api.get<BillingCycleDetail>(`/api/v1/towers/${towerId}/billing-cycles/${cycleId}`);
}

/**
 * `201` (sync, <=300 active flats) vs `202` (async, job enqueued) share the
 * same request — the caller inspects `status` to decide whether to close the
 * dialog immediately or switch to the polling/progress state. See
 * specs/03-maintenance-billing/backend.md §4 and frontend.md §2.3.
 */
export function createBillingCycle(
  towerId: string,
  input: { month: number; year: number; due_date: string }
): Promise<ResponseWithStatus<BillingCycle | BillingCycleJobAccepted>> {
  return apiFetchWithStatus<BillingCycle | BillingCycleJobAccepted>(`/api/v1/towers/${towerId}/billing-cycles`, {
    method: "POST",
    body: input,
  });
}

// --- 6.4 Dues --------------------------------------------------------------

export function listCycleDues(
  towerId: string,
  cycleId: string,
  params?: { status?: MaintenanceDueStatus; page?: number; page_size?: number }
) {
  return api.get<Paginated<MaintenanceDue>>(`/api/v1/towers/${towerId}/billing-cycles/${cycleId}/dues`, { params });
}

/**
 * Cross-cycle "at a glance" dues list — PRD §6.3.4, frontend.md §2.5.
 *
 * `cycle_id` is passed as a best-effort query param: backend.md §6.4
 * documents this route's query as `status=pending|overdue` only (no
 * cycle-scoping param), and `MaintenanceDueOut` (backend.md §7) carries no
 * cycle identifier a client could filter on locally either. frontend.md
 * §2.5 nonetheless calls for "an added Select filter for billing cycle
 * (optional, defaults to 'All Cycles')" on this page — there is no
 * documented mechanism to implement that filter without one. This param is
 * forward-compatible plumbing pending backend confirmation; see
 * dues-client.tsx for where it's wired to the cycle `Select`.
 */
export function listTowerDues(
  towerId: string,
  params?: {
    status?: Exclude<MaintenanceDueStatus, "paid">;
    cycle_id?: string;
    page?: number;
    page_size?: number;
  }
) {
  return api.get<Paginated<MaintenanceDue>>(`/api/v1/towers/${towerId}/dues`, { params });
}

/**
 * `cycleId` is passed as a best-effort `?cycle_id=` query param: backend.md
 * §6.4's route table documents this endpoint with no cycle-scoping
 * parameter, but frontend.md §2.4 requires the cycle-detail page's stat
 * cards to be "scoped to this cycle." Until the backend contract is
 * confirmed either way, the cycle-detail page (see cycle-detail-client.tsx)
 * primarily sources Total Collected / Pending Count from the cycle's own
 * documented aggregate fields (`BillingCycleOut.total_collected`/
 * `.pending_count`) and only falls back to this endpoint for
 * `overdue_amount`, which has no equivalent on the cycle aggregate.
 */
export function getBillingDashboardStats(towerId: string, cycleId?: string) {
  return api.get<BillingDashboardStats>(`/api/v1/towers/${towerId}/billing-dashboard-stats`, {
    params: cycleId ? { cycle_id: cycleId } : undefined,
  });
}

export function getDue(towerId: string, dueId: string) {
  return api.get<MaintenanceDue>(`/api/v1/towers/${towerId}/dues/${dueId}`);
}

export function markDuePaid(
  towerId: string,
  dueId: string,
  input: {
    payment_date: string;
    amount_received: number;
    payment_mode: PaymentMode;
    reference_number?: string | null;
  }
) {
  return api.patch<MarkPaidResponse>(`/api/v1/towers/${towerId}/dues/${dueId}/mark-paid`, input);
}

export function getDueReceipt(towerId: string, dueId: string) {
  return api.get<{ receipt_number: string; download_url: string }>(
    `/api/v1/towers/${towerId}/dues/${dueId}/receipt`
  );
}
