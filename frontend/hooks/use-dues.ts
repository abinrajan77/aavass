import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getBillingDashboardStats, listCycleDues, listTowerDues, markDuePaid } from "@/lib/api/billing";
import type { MaintenanceDueStatus, PaymentMode } from "@/lib/api/types";

/**
 * TanStack Query hooks for the dues list/detail screens —
 * specs/03-maintenance-billing/frontend.md §2.4/§2.5.
 */

export function useCycleDues(towerId: string, cycleId: string, status?: MaintenanceDueStatus | "all") {
  return useQuery({
    queryKey: ["cycle-dues", towerId, cycleId, status ?? "all"],
    queryFn: () =>
      listCycleDues(towerId, cycleId, {
        page: 1,
        page_size: 100,
        status: status && status !== "all" ? status : undefined,
      }),
  });
}

/**
 * Cross-cycle "at a glance" dues list. Backend.md §6.4 documents the query
 * enum as `status=pending|overdue` only (no `paid`) — matching the route's
 * stated purpose, PRD §6.3.4's "pending/overdue at a glance" dashboard
 * drill-down. The "All" tab omits the filter entirely.
 */
export function useTowerDues(towerId: string, status?: "pending" | "overdue" | "all", cycleId?: string) {
  return useQuery({
    queryKey: ["tower-dues", towerId, status ?? "all", cycleId ?? "all-cycles"],
    queryFn: () =>
      listTowerDues(towerId, {
        page: 1,
        page_size: 100,
        status: status && status !== "all" ? status : undefined,
        cycle_id: cycleId,
      }),
  });
}

export function useBillingDashboardStats(towerId: string, cycleId?: string) {
  return useQuery({
    queryKey: ["billing-dashboard-stats", towerId, cycleId ?? "tower-wide"],
    queryFn: () => getBillingDashboardStats(towerId, cycleId),
  });
}

export function useMarkDuePaid(towerId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      dueId,
      ...input
    }: {
      dueId: string;
      payment_date: string;
      amount_received: number;
      payment_mode: PaymentMode;
      reference_number?: string | null;
    }) => markDuePaid(towerId, dueId, input),
    onSuccess: () => {
      // Broad invalidation across every dues/stats view that could show this
      // due — cycle-scoped list, cross-cycle list, and the dashboard stat
      // cards all need to reflect the new Paid status/collected total.
      queryClient.invalidateQueries({ queryKey: ["cycle-dues", towerId] });
      queryClient.invalidateQueries({ queryKey: ["tower-dues", towerId] });
      queryClient.invalidateQueries({ queryKey: ["billing-dashboard-stats", towerId] });
      queryClient.invalidateQueries({ queryKey: ["billing-cycles", towerId] });
    },
  });
}
