"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as flatsApi from "@/lib/api/flats";
import { updateOwner, type OwnerUpdateInput } from "@/lib/api/owners";
import type { FlatType, OccupancyStatus } from "@/lib/api/types";

/**
 * Query key factory for Module 2 — shared across the admin
 * (/towers/[towerId]/flats*) and owner (/my-flats/[flatId]) surfaces so a
 * mutation triggered from either one invalidates the same cached queries
 * the other surface reads. This matters specifically because
 * `occupancy_status` is a side effect of tenant add/vacate (frontend.md:
 * "adding a tenant invalidates both the tenant list and the flat detail
 * query, since occupancy_status changes as a side effect") and because both
 * surfaces read the exact same underlying data (frontend.md E2E scenario:
 * "tenant appears immediately in the admin's ... Tenants tab").
 */
export const flatKeys = {
  all: ["flats"] as const,
  list: (towerId: string, filters?: Record<string, unknown>) => ["flats", towerId, filters] as const,
  detail: (towerId: string, flatId: string) => ["flat", towerId, flatId] as const,
  owners: (towerId: string, flatId: string) => ["flat-owners", towerId, flatId] as const,
  tenants: (towerId: string, flatId: string) => ["flat-tenants", towerId, flatId] as const,
  myFlats: () => ["my-flats"] as const,
};

export function useFlatsQuery(
  towerId: string,
  filters?: { type?: FlatType; occupancy_status?: OccupancyStatus; q?: string }
) {
  return useQuery({
    queryKey: flatKeys.list(towerId, filters),
    queryFn: () => flatsApi.listFlats(towerId, { page: 1, page_size: 100, ...filters }),
  });
}

export function useFlatQuery(towerId: string | undefined, flatId: string | undefined) {
  return useQuery({
    queryKey: flatKeys.detail(towerId ?? "", flatId ?? ""),
    queryFn: () => flatsApi.getFlat(towerId as string, flatId as string),
    enabled: Boolean(towerId && flatId),
  });
}

export function useFlatOwnersQuery(towerId: string | undefined, flatId: string | undefined) {
  return useQuery({
    queryKey: flatKeys.owners(towerId ?? "", flatId ?? ""),
    queryFn: () => flatsApi.listFlatOwners(towerId as string, flatId as string),
    enabled: Boolean(towerId && flatId),
  });
}

export function useFlatTenantsQuery(towerId: string | undefined, flatId: string | undefined) {
  return useQuery({
    queryKey: flatKeys.tenants(towerId ?? "", flatId ?? ""),
    queryFn: () => flatsApi.listFlatTenants(towerId as string, flatId as string),
    enabled: Boolean(towerId && flatId),
  });
}

export function useMyFlatsQuery() {
  return useQuery({ queryKey: flatKeys.myFlats(), queryFn: () => flatsApi.getMyFlats() });
}

/**
 * Every mutation in this module ends up touching at least one of: the flats
 * list (occupancy/primary-owner columns), the flat detail (primary_owner /
 * active_tenant / occupancy_status), the owners sub-list, the tenants
 * sub-list, or the owner's cross-tower `/me/flats` list. Given this is a
 * low-traffic CRUD surface (not a high-frequency dashboard), invalidating
 * all five on every mutation is simpler and safer than hand-picking a
 * narrower set per mutation and risking a stale badge/column — the exact
 * regression frontend.md's test plan is guarding against.
 */
function useInvalidateFlat(towerId: string, flatId?: string) {
  const queryClient = useQueryClient();
  return () => {
    queryClient.invalidateQueries({ queryKey: flatKeys.all });
    queryClient.invalidateQueries({ queryKey: flatKeys.myFlats() });
    if (flatId) {
      queryClient.invalidateQueries({ queryKey: flatKeys.detail(towerId, flatId) });
      queryClient.invalidateQueries({ queryKey: flatKeys.owners(towerId, flatId) });
      queryClient.invalidateQueries({ queryKey: flatKeys.tenants(towerId, flatId) });
    }
  };
}

export function useCreateFlatMutation(towerId: string) {
  const invalidate = useInvalidateFlat(towerId);
  return useMutation({
    mutationFn: (input: flatsApi.FlatCreateInput) => flatsApi.createFlat(towerId, input),
    onSuccess: invalidate,
  });
}

export function useUpdateFlatMutation(towerId: string, flatId: string) {
  const invalidate = useInvalidateFlat(towerId, flatId);
  return useMutation({
    mutationFn: (input: Partial<flatsApi.FlatCreateInput>) => flatsApi.updateFlat(towerId, flatId, input),
    onSuccess: invalidate,
  });
}

export function useDeactivateFlatMutation(towerId: string, flatId: string) {
  const invalidate = useInvalidateFlat(towerId, flatId);
  return useMutation({
    mutationFn: () => flatsApi.deactivateFlat(towerId, flatId),
    onSuccess: invalidate,
  });
}

export function useReactivateFlatMutation(towerId: string, flatId: string) {
  const invalidate = useInvalidateFlat(towerId, flatId);
  return useMutation({
    mutationFn: () => flatsApi.reactivateFlat(towerId, flatId),
    onSuccess: invalidate,
  });
}

export function useAddFlatOwnerMutation(towerId: string, flatId: string) {
  const invalidate = useInvalidateFlat(towerId, flatId);
  return useMutation({
    mutationFn: (input: flatsApi.AddFlatOwnerInput) => flatsApi.addFlatOwner(towerId, flatId, input),
    onSuccess: invalidate,
  });
}

export function useUpdateFlatOwnershipMutation(towerId: string, flatId: string) {
  const invalidate = useInvalidateFlat(towerId, flatId);
  return useMutation({
    mutationFn: ({
      ownershipId,
      input,
    }: {
      ownershipId: string;
      input: flatsApi.FlatOwnershipUpdateInput;
    }) => flatsApi.updateFlatOwnership(towerId, flatId, ownershipId, input),
    onSuccess: invalidate,
  });
}

export function useRemoveFlatOwnershipMutation(towerId: string, flatId: string) {
  const invalidate = useInvalidateFlat(towerId, flatId);
  return useMutation({
    mutationFn: ({
      ownershipId,
      input,
    }: {
      ownershipId: string;
      input: flatsApi.RemoveFlatOwnershipInput;
    }) => flatsApi.removeFlatOwnership(towerId, flatId, ownershipId, input),
    onSuccess: invalidate,
  });
}

export function useUpdateOwnerContactMutation(towerId: string, flatId: string) {
  const invalidate = useInvalidateFlat(towerId, flatId);
  return useMutation({
    mutationFn: ({ ownerId, input }: { ownerId: string; input: OwnerUpdateInput }) =>
      updateOwner(ownerId, input),
    onSuccess: invalidate,
  });
}

export function useCreateTenantMutation(towerId: string, flatId: string) {
  const invalidate = useInvalidateFlat(towerId, flatId);
  return useMutation({
    mutationFn: (input: flatsApi.TenantCreateInput) => flatsApi.createFlatTenant(towerId, flatId, input),
    onSuccess: invalidate,
  });
}

export function useUpdateTenantMutation(towerId: string, flatId: string) {
  const invalidate = useInvalidateFlat(towerId, flatId);
  return useMutation({
    mutationFn: ({ tenantId, input }: { tenantId: string; input: flatsApi.TenantUpdateInput }) =>
      flatsApi.updateFlatTenant(towerId, flatId, tenantId, input),
    onSuccess: invalidate,
  });
}

export function useVacateTenantMutation(towerId: string, flatId: string) {
  const invalidate = useInvalidateFlat(towerId, flatId);
  return useMutation({
    mutationFn: ({ tenantId, input }: { tenantId: string; input: flatsApi.TenantVacateInput }) =>
      flatsApi.vacateFlatTenant(towerId, flatId, tenantId, input),
    onSuccess: invalidate,
  });
}
