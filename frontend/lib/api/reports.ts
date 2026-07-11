import { api, apiFetchFileOrJson } from "./client";
import type {
  CollectionReportResponse,
  CollectionVsExpenditureResponse,
  ExpenditureReportResponse,
  OutstandingDuesReportResponse,
  ReportPeriodType,
  TenantRegisterResponse,
} from "./types";

/**
 * Module 5 report endpoints — mirrors
 * specs/05-reporting-owner-portal-notifications/backend.md §2 route-by-route.
 * Tower-scoped throughout, per specs/00-architecture-and-standards.md §6.
 */

export type ReportType =
  | "collection"
  | "outstanding_dues"
  | "expenditure"
  | "collection_vs_expenditure"
  | "tenant_register";

export type ReportFormat = "pdf" | "csv";

/** URL path segment per report type — backend.md §2.1-§2.5's route table. */
const REPORT_PATH: Record<ReportType, string> = {
  collection: "collection",
  outstanding_dues: "outstanding-dues",
  expenditure: "expenditure",
  collection_vs_expenditure: "collection-vs-expenditure",
  tenant_register: "tenant-register",
};

// --- §2.1 Monthly Collection Report ----------------------------------------

export function getCollectionReport(towerId: string, billingCycleId: string) {
  return api.get<CollectionReportResponse>(`/api/v1/towers/${towerId}/reports/collection`, {
    params: { billing_cycle_id: billingCycleId },
  });
}

// --- §2.2 Outstanding Dues Report -------------------------------------------

export function getOutstandingDuesReport(towerId: string, asOfDate?: string) {
  return api.get<OutstandingDuesReportResponse>(`/api/v1/towers/${towerId}/reports/outstanding-dues`, {
    params: asOfDate ? { as_of_date: asOfDate } : undefined,
  });
}

// --- §2.3 Expenditure Report -------------------------------------------------

export function getExpenditureReport(towerId: string, periodStart: string, periodEnd: string) {
  return api.get<ExpenditureReportResponse>(`/api/v1/towers/${towerId}/reports/expenditure`, {
    params: { period_start: periodStart, period_end: periodEnd },
  });
}

// --- §2.4 Collection vs Expenditure Summary ----------------------------------

export function getCollectionVsExpenditureReport(
  towerId: string,
  params: { period_type: ReportPeriodType; month?: number; year: number }
) {
  return api.get<CollectionVsExpenditureResponse>(`/api/v1/towers/${towerId}/reports/collection-vs-expenditure`, {
    params,
  });
}

// --- §2.5 Tenant Register -----------------------------------------------------

export function getTenantRegisterReport(towerId: string) {
  return api.get<TenantRegisterResponse>(`/api/v1/towers/${towerId}/reports/tenant-register`);
}

// --- §2.6 Export flow (shared across all 5 report types) --------------------

export interface ExportJobAccepted {
  job_id: string;
}

export type ExportResult =
  | { kind: "file"; blob: Blob; filename: string }
  | { kind: "job"; jobId: string };

/**
 * Calls the same report endpoint as the JSON preview, but with `format` set
 * — the backend estimates row count and either streams the rendered file
 * synchronously (<=5000 rows, `200`) or enqueues a background job and
 * returns `202 { job_id }` (>5000 rows), per backend.md §2.6. The frontend
 * branches on the result `kind`, never on report type, to decide whether to
 * download immediately or switch into the poll-then-download state.
 */
export async function exportReport(
  towerId: string,
  reportType: ReportType,
  format: ReportFormat,
  params: Record<string, string | number | boolean | undefined>
): Promise<ExportResult> {
  const result = await apiFetchFileOrJson<ExportJobAccepted>(
    `/api/v1/towers/${towerId}/reports/${REPORT_PATH[reportType]}`,
    { params: { ...params, format } }
  );

  if (result.kind === "accepted") {
    return { kind: "job", jobId: result.data.job_id };
  }

  return {
    kind: "file",
    blob: result.blob,
    filename: result.filename ?? `${reportType}.${format}`,
  };
}
