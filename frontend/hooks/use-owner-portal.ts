import { useQuery } from "@tanstack/react-query";
import { getOwnedFlatsSummary, getOwnerFlatDashboard } from "@/lib/api/owner-portal";

/**
 * TanStack Query hooks for the owner self-service portal —
 * specs/05-reporting-owner-portal-notifications/backend.md §3. Query keys
 * are per-flat (`ownerDashboard`) so switching flats via the Command-palette
 * `FlatSwitcher` and navigating to a fresh `/my-flats/[flatId]/dashboard`
 * route never serves cached data from the previously-viewed flat — see
 * overview.md's "owner with flats in 3 towers switches context" edge case.
 */

export const ownerPortalKeys = {
  flatsSummary: () => ["owner-flats-summary"] as const,
  dashboard: (flatId: string) => ["owner-flat-dashboard", flatId] as const,
};

export function useOwnedFlatsSummary() {
  return useQuery({ queryKey: ownerPortalKeys.flatsSummary(), queryFn: getOwnedFlatsSummary });
}

export function useOwnerFlatDashboard(flatId: string) {
  return useQuery({
    queryKey: ownerPortalKeys.dashboard(flatId),
    queryFn: () => getOwnerFlatDashboard(flatId),
    enabled: Boolean(flatId),
  });
}
