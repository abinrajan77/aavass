import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createGracePeriodConfig,
  createMaintenanceFormula,
  getCurrentGracePeriodConfig,
  getCurrentMaintenanceFormula,
  listGracePeriodConfigs,
  listMaintenanceFormulas,
} from "@/lib/api/billing";
import { ApiError } from "@/lib/api/client";

/**
 * TanStack Query hooks for Module 3's versioned config screens
 * (specs/03-maintenance-billing/frontend.md §2.1/§2.2) — mirrors the pattern
 * used in association-members-client.tsx / tower-profile-form.tsx (inline
 * useQuery/useMutation there; extracted to hooks here since formula +
 * grace-period each need both a "current" and a "history" query reused
 * across their form + version-history table).
 */

export function useCurrentMaintenanceFormula(towerId: string) {
  return useQuery({
    queryKey: ["maintenance-formula-current", towerId],
    queryFn: () => getCurrentMaintenanceFormula(towerId),
    retry: (failureCount, error) => {
      // 404 NO_FORMULA_CONFIGURED is an expected "not set up yet" state, not
      // a transient failure — don't retry it.
      if (error instanceof ApiError && error.status === 404) return false;
      return failureCount < 2;
    },
  });
}

export function useMaintenanceFormulaHistory(towerId: string) {
  return useQuery({
    queryKey: ["maintenance-formula-history", towerId],
    queryFn: () => listMaintenanceFormulas(towerId, { page: 1, page_size: 100 }),
  });
}

export function useCreateMaintenanceFormula(towerId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { base_amount: number; per_sqft_rate: number; effective_from?: string }) =>
      createMaintenanceFormula(towerId, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["maintenance-formula-current", towerId] });
      queryClient.invalidateQueries({ queryKey: ["maintenance-formula-history", towerId] });
    },
  });
}

export function useCurrentGracePeriodConfig(towerId: string) {
  return useQuery({
    queryKey: ["grace-period-current", towerId],
    queryFn: () => getCurrentGracePeriodConfig(towerId),
  });
}

export function useGracePeriodHistory(towerId: string) {
  return useQuery({
    queryKey: ["grace-period-history", towerId],
    queryFn: () => listGracePeriodConfigs(towerId, { page: 1, page_size: 100 }),
  });
}

export function useCreateGracePeriodConfig(towerId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { grace_period_days: number }) => createGracePeriodConfig(towerId, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["grace-period-current", towerId] });
      queryClient.invalidateQueries({ queryKey: ["grace-period-history", towerId] });
    },
  });
}
