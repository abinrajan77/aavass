"use client";

import { ColumnDef } from "@tanstack/react-table";
import { toast } from "sonner";
import { DataTable } from "@/components/data-table/data-table";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Can } from "@/components/auth/can";
import { PERMISSIONS } from "@/lib/permissions";
import { BillingConfigTabs } from "@/components/billing/billing-config-tabs";
import { FormulaForm } from "@/components/billing/formula-form";
import { useCreateMaintenanceFormula, useCurrentMaintenanceFormula, useMaintenanceFormulaHistory } from "@/hooks/use-billing";
import type { MaintenanceFormula } from "@/lib/api/types";
import { ApiError } from "@/lib/api/client";

/** /towers/[towerId]/billing/formula — frontend.md §2.1. */
export function FormulaClient({ towerId }: { towerId: string }) {
  const currentQuery = useCurrentMaintenanceFormula(towerId);
  const historyQuery = useMaintenanceFormulaHistory(towerId);
  const createMutation = useCreateMaintenanceFormula(towerId);

  // 404 NO_FORMULA_CONFIGURED is expected for a brand-new tower — not an error state.
  const notConfigured = currentQuery.error instanceof ApiError && currentQuery.error.status === 404;

  function handleSubmit(values: { base_amount: number; per_sqft_rate: number; effective_from: Date }) {
    createMutation.mutate(
      {
        base_amount: values.base_amount,
        per_sqft_rate: values.per_sqft_rate,
        effective_from: values.effective_from.toISOString().slice(0, 10),
      },
      {
        onSuccess: () => toast.success("Maintenance formula saved"),
        onError: () => toast.error("Couldn't save the maintenance formula"),
      }
    );
  }

  const columns: ColumnDef<MaintenanceFormula>[] = [
    {
      accessorKey: "base_amount",
      header: "Base Amount",
      cell: ({ row }) => `₹${row.original.base_amount.toLocaleString("en-IN", { minimumFractionDigits: 2 })}`,
    },
    {
      accessorKey: "per_sqft_rate",
      header: "Per Sq.Ft. Rate",
      cell: ({ row }) => `₹${row.original.per_sqft_rate.toLocaleString("en-IN", { minimumFractionDigits: 2 })}`,
    },
    { accessorKey: "effective_from", header: "Effective From" },
    {
      id: "changed_by",
      header: "Changed By",
      cell: ({ row }) => row.original.created_by_name ?? row.original.created_by,
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold text-foreground">Maintenance Billing</h1>
        <p className="text-sm text-muted-foreground">Configure the formula and grace period for this tower.</p>
      </div>

      <BillingConfigTabs towerId={towerId} active="formula" />

      <Card>
        <CardHeader>
          <CardTitle>Maintenance formula</CardTitle>
          <CardDescription>
            Monthly Maintenance = Base Amount + (Carpet Area × Per Sq.Ft. Rate). Applies uniformly to every flat
            in the tower — there is no per-flat override.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {currentQuery.isLoading ? (
            <div className="space-y-3">
              <Skeleton className="h-9 w-full" />
              <Skeleton className="h-9 w-full" />
            </div>
          ) : (
            <Can
              permission={PERMISSIONS.CONFIGURE_BILLING}
              fallback={
                currentQuery.data ? (
                  <dl className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-3">
                    <div>
                      <dt className="text-muted-foreground">Base Amount</dt>
                      <dd className="font-medium">₹{currentQuery.data.base_amount}</dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground">Per Sq.Ft. Rate</dt>
                      <dd className="font-medium">₹{currentQuery.data.per_sqft_rate}</dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground">Effective From</dt>
                      <dd className="font-medium">{currentQuery.data.effective_from}</dd>
                    </div>
                  </dl>
                ) : (
                  <p className="text-sm text-muted-foreground">No formula configured yet.</p>
                )
              }
            >
              <FormulaForm
                defaultValues={
                  notConfigured || !currentQuery.data
                    ? undefined
                    : {
                        base_amount: currentQuery.data.base_amount,
                        per_sqft_rate: currentQuery.data.per_sqft_rate,
                      }
                }
                onSubmit={handleSubmit}
                isSubmitting={createMutation.isPending}
              />
            </Can>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Version history</CardTitle>
          <CardDescription>Newest first — formula changes never retroact onto past billing cycles.</CardDescription>
        </CardHeader>
        <CardContent>
          <DataTable
            columns={columns}
            data={historyQuery.data?.items ?? []}
            isLoading={historyQuery.isLoading}
            emptyMessage="No formula versions yet."
          />
        </CardContent>
      </Card>
    </div>
  );
}
