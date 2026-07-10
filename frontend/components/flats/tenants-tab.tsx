"use client";

import { useState } from "react";
import { ColumnDef } from "@tanstack/react-table";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DataTable } from "@/components/data-table/data-table";
import { Skeleton } from "@/components/ui/skeleton";
import { AddTenantDialog } from "./add-tenant-dialog";
import { VacateTenantDialog } from "./vacate-tenant-dialog";
import { useFlatTenantsQuery } from "@/lib/hooks/use-flats";
import type { Tenant } from "@/lib/api/types";

/**
 * Tenants tab — frontend.md: current active tenant card (with "Vacate") if
 * one exists, else "Add Tenant"; below, a read-only Tenant History
 * DataTable sorted lease_start desc (backend.md already returns this order —
 * "active first, then past ordered by lease_start desc" — so this
 * component trusts API order rather than re-sorting).
 *
 * `canManage` gates Add/Vacate — true for MANAGE_RESIDENTS (admin) and for
 * MANAGE_OWN_FLAT on the caller's own flat (frontend.md: "owners can Add
 * Tenant and Vacate Tenant").
 */
export function TenantsTab({
  towerId,
  flatId,
  canManage,
}: {
  towerId: string;
  flatId: string;
  canManage: boolean;
}) {
  const tenantsQuery = useFlatTenantsQuery(towerId, flatId);
  const [vacateTarget, setVacateTarget] = useState<Tenant | null>(null);

  if (tenantsQuery.isLoading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }

  const tenants = tenantsQuery.data ?? [];
  const activeTenant = tenants.find((t) => t.is_active) ?? null;
  const history = tenants.filter((t) => !t.is_active);

  const historyColumns: ColumnDef<Tenant>[] = [
    { accessorKey: "full_name", header: "Name" },
    { accessorKey: "phone", header: "Phone" },
    { accessorKey: "lease_start", header: "Lease start" },
    { accessorKey: "lease_end", header: "Lease end" },
    {
      id: "vacated_at",
      header: "Vacated",
      cell: ({ row }) => row.original.vacated_at ?? "—",
    },
  ];

  return (
    <div className="space-y-6">
      {activeTenant ? (
        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <CardTitle className="text-base">Current tenant</CardTitle>
            {canManage ? (
              <Button variant="outline" onClick={() => setVacateTarget(activeTenant)}>
                Vacate
              </Button>
            ) : null}
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <p className="text-muted-foreground">Name</p>
              <p className="text-foreground">{activeTenant.full_name}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Phone</p>
              <p className="text-foreground">{activeTenant.phone}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Email</p>
              <p className="text-foreground">{activeTenant.email ?? "—"}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Lease</p>
              <p className="text-foreground">
                {activeTenant.lease_start} — {activeTenant.lease_end ?? "ongoing"}
              </p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="flex items-center justify-between rounded-md border border-dashed border-border p-4">
          <p className="text-sm text-muted-foreground">This flat has no active tenant.</p>
          {canManage ? <AddTenantDialog towerId={towerId} flatId={flatId} /> : null}
        </div>
      )}

      <div>
        <h3 className="mb-2 text-sm font-medium text-foreground">Tenant history</h3>
        <DataTable columns={historyColumns} data={history} emptyMessage="No past tenants." />
      </div>

      <VacateTenantDialog
        towerId={towerId}
        flatId={flatId}
        tenant={vacateTarget}
        open={!!vacateTarget}
        onOpenChange={(open) => !open && setVacateTarget(null)}
      />
    </div>
  );
}
