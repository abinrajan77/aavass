import { useQuery } from "@tanstack/react-query";
import {
  getCollectionReport,
  getCollectionVsExpenditureReport,
  getExpenditureReport,
  getOutstandingDuesReport,
  getTenantRegisterReport,
} from "@/lib/api/reports";
import type { ReportPeriodType } from "@/lib/api/types";

/**
 * TanStack Query hooks for the 5 report preview payloads —
 * specs/05-reporting-owner-portal-notifications/frontend.md §2 ("`DataTable`
 * ... renders the JSON preview (endpoint called without `format`) before
 * export"). Export (PDF/CSV) is handled separately by
 * `components/reports/export-buttons.tsx`, which calls the same underlying
 * endpoint with `format` set via `lib/api/reports.ts#exportReport`.
 */

export function useCollectionReport(towerId: string, billingCycleId: string | undefined) {
  return useQuery({
    queryKey: ["report-collection", towerId, billingCycleId],
    queryFn: () => getCollectionReport(towerId, billingCycleId as string),
    enabled: Boolean(billingCycleId),
  });
}

export function useOutstandingDuesReport(towerId: string, asOfDate: string | undefined) {
  return useQuery({
    queryKey: ["report-outstanding-dues", towerId, asOfDate],
    queryFn: () => getOutstandingDuesReport(towerId, asOfDate),
  });
}

export function useExpenditureReport(
  towerId: string,
  periodStart: string | undefined,
  periodEnd: string | undefined
) {
  return useQuery({
    queryKey: ["report-expenditure", towerId, periodStart, periodEnd],
    queryFn: () => getExpenditureReport(towerId, periodStart as string, periodEnd as string),
    enabled: Boolean(periodStart && periodEnd),
  });
}

export function useCollectionVsExpenditureReport(
  towerId: string,
  params: { period_type: ReportPeriodType; month?: number; year: number } | undefined
) {
  return useQuery({
    queryKey: ["report-collection-vs-expenditure", towerId, params],
    queryFn: () => getCollectionVsExpenditureReport(towerId, params!),
    enabled: Boolean(params),
  });
}

export function useTenantRegisterReport(towerId: string) {
  return useQuery({
    queryKey: ["report-tenant-register", towerId],
    queryFn: () => getTenantRegisterReport(towerId),
  });
}
