import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createBillingCycle, getBillingCycle, listBillingCycles } from "@/lib/api/billing";

/**
 * TanStack Query hooks for billing-cycle list/detail/generation —
 * specs/03-maintenance-billing/frontend.md §2.3.
 */

export function useBillingCycles(towerId: string) {
  return useQuery({
    queryKey: ["billing-cycles", towerId],
    queryFn: () => listBillingCycles(towerId, { page: 1, page_size: 100 }),
  });
}

export function useBillingCycle(towerId: string, cycleId: string) {
  return useQuery({
    queryKey: ["billing-cycle", towerId, cycleId],
    queryFn: () => getBillingCycle(towerId, cycleId),
  });
}

/**
 * Wraps `createBillingCycle`, which returns `{ status, data }` since the
 * same endpoint answers `201` (sync) or `202` (async, job enqueued) — see
 * specs/03-maintenance-billing/backend.md §4. The caller (GenerateCycleDialog)
 * branches on `result.status` to decide whether to close immediately or
 * switch into the polling/progress state.
 */
export function useCreateBillingCycle(towerId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { month: number; year: number; due_date: string }) => createBillingCycle(towerId, input),
    onSuccess: (result) => {
      // For the sync (201) path the cycle is already active; for the async
      // (202) path this just refreshes the list so the new "generating" row
      // shows up immediately — the caller separately polls the job and
      // invalidates again once it's done.
      if (result.status === 201 || result.status === 202) {
        queryClient.invalidateQueries({ queryKey: ["billing-cycles", towerId] });
      }
    },
  });
}
