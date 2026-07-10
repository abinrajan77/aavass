"use client";

import { useRouter } from "next/navigation";
import { ColumnDef } from "@tanstack/react-table";
import { DataTable } from "@/components/data-table/data-table";
import { Badge } from "@/components/ui/badge";
import { Can } from "@/components/auth/can";
import { PERMISSIONS } from "@/lib/permissions";
import { GenerateCycleDialog } from "@/components/billing/generate-cycle-dialog";
import { useBillingCycles } from "@/hooks/use-billing-cycles";
import type { BillingCycle } from "@/lib/api/types";

const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

/** /towers/[towerId]/billing/cycles — frontend.md §2.3. */
export function CyclesClient({ towerId }: { towerId: string }) {
  const router = useRouter();
  const cyclesQuery = useBillingCycles(towerId);

  const columns: ColumnDef<BillingCycle>[] = [
    {
      id: "period",
      header: "Month/Year",
      cell: ({ row }) => `${MONTH_NAMES[row.original.month - 1]} ${row.original.year}`,
    },
    { accessorKey: "due_date", header: "Due Date" },
    {
      accessorKey: "status",
      header: "Status",
      // Cycle-generation status is a distinct concept from due payment
      // status (Paid/Pending/Overdue) — per frontend.md §2.3 it uses
      // muted/outline for "generating" and the plain default badge for
      // "active", deliberately NOT the success/warning/destructive tokens
      // reserved for payment status (00-architecture-and-standards.md §3.1).
      cell: ({ row }) =>
        row.original.status === "generating" ? (
          <Badge variant="mutedOutline">Generating…</Badge>
        ) : (
          <Badge>Active</Badge>
        ),
    },
    {
      accessorKey: "total_dues",
      header: "Total Dues",
    },
    {
      accessorKey: "total_collected",
      header: "Total Collected",
      cell: ({ row }) => `₹${row.original.total_collected.toLocaleString("en-IN", { minimumFractionDigits: 2 })}`,
    },
    { accessorKey: "pending_count", header: "Pending Count" },
    { accessorKey: "overdue_count", header: "Overdue Count" },
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-foreground">Billing cycles</h1>
          <p className="text-sm text-muted-foreground">Generate and review monthly maintenance billing cycles.</p>
        </div>
        <Can permission={PERMISSIONS.CREATE_BILLING_CYCLE}>
          <GenerateCycleDialog towerId={towerId} />
        </Can>
      </div>

      <DataTable
        columns={columns}
        data={cyclesQuery.data?.items ?? []}
        isLoading={cyclesQuery.isLoading}
        onRowClick={(cycle) => router.push(`/towers/${towerId}/billing/cycles/${cycle.id}`)}
        emptyMessage="No billing cycles generated yet."
      />
    </div>
  );
}
