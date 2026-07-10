"use client";

import { ColumnDef } from "@tanstack/react-table";
import { toast } from "sonner";
import { DataTable } from "@/components/data-table/data-table";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Can } from "@/components/auth/can";
import { PERMISSIONS } from "@/lib/permissions";
import { BillingConfigTabs } from "@/components/billing/billing-config-tabs";
import { GracePeriodForm } from "@/components/billing/grace-period-form";
import {
  useCreateGracePeriodConfig,
  useCurrentGracePeriodConfig,
  useGracePeriodHistory,
} from "@/hooks/use-billing";
import type { GracePeriodConfig } from "@/lib/api/types";

/** /towers/[towerId]/billing/grace-period — frontend.md §2.2. */
export function GracePeriodClient({ towerId }: { towerId: string }) {
  const currentQuery = useCurrentGracePeriodConfig(towerId);
  const historyQuery = useGracePeriodHistory(towerId);
  const createMutation = useCreateGracePeriodConfig(towerId);

  const columns: ColumnDef<GracePeriodConfig>[] = [
    { accessorKey: "grace_period_days", header: "Grace Period (days)" },
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

      <BillingConfigTabs towerId={towerId} active="grace-period" />

      <Card>
        <CardHeader>
          <CardTitle>Grace period</CardTitle>
          <CardDescription>
            Number of days after a due date before an unpaid due is flagged Overdue.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {currentQuery.isLoading ? (
            <Skeleton className="h-9 w-full" />
          ) : (
            <Can
              permission={PERMISSIONS.CONFIGURE_BILLING}
              fallback={
                <p className="text-sm">
                  Current grace period:{" "}
                  <span className="font-medium">{currentQuery.data?.grace_period_days ?? 0} days</span>
                </p>
              }
            >
              <GracePeriodForm
                defaultValues={{ grace_period_days: currentQuery.data?.grace_period_days ?? 0 }}
                onSubmit={(values) =>
                  createMutation.mutate(values, {
                    onSuccess: () => toast.success("Grace period saved"),
                    onError: () => toast.error("Couldn't save the grace period"),
                  })
                }
                isSubmitting={createMutation.isPending}
              />
            </Can>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Version history</CardTitle>
          <CardDescription>
            Newest first — grace-period changes never retroact onto past billing cycles.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <DataTable
            columns={columns}
            data={historyQuery.data?.items ?? []}
            isLoading={historyQuery.isLoading}
            emptyMessage="No grace-period versions yet."
          />
        </CardContent>
      </Card>
    </div>
  );
}
