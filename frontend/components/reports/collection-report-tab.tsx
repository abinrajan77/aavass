"use client";

import { useMemo, useState } from "react";
import { ColumnDef } from "@tanstack/react-table";
import { format } from "date-fns";
import { DataTable } from "@/components/data-table/data-table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ExportButtons } from "./export-buttons";
import { ReportEmptyState } from "./report-empty-state";
import { ReportStatusBadge } from "./report-status-badge";
import { useBillingCycles } from "@/hooks/use-billing-cycles";
import { useCollectionReport } from "@/hooks/use-reports";
import { formatCurrency } from "@/lib/utils";
import type { CollectionReportRow } from "@/lib/api/types";

const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

/**
 * Monthly Collection Report — specs/05-reporting-owner-portal-notifications/
 * frontend.md §2: period control is a `Select` bound to the tower's
 * `BillingCycle` list (Module 3 data, reused via `useBillingCycles`).
 */
export function CollectionReportTab({ towerId }: { towerId: string }) {
  const cyclesQuery = useBillingCycles(towerId);
  const cycles = useMemo(() => cyclesQuery.data?.items ?? [], [cyclesQuery.data]);
  const [selectedCycleId, setSelectedCycleId] = useState<string | undefined>(undefined);

  const activeCycleId = selectedCycleId ?? cycles[0]?.id;
  const reportQuery = useCollectionReport(towerId, activeCycleId);
  const items = reportQuery.data?.items ?? [];

  const columns: ColumnDef<CollectionReportRow>[] = useMemo(
    () => [
      { accessorKey: "flat_number", header: "Flat" },
      { id: "owners", header: "Owner(s)", cell: ({ row }) => row.original.owner_names.join(", ") || "—" },
      {
        id: "resident",
        header: "Resident",
        cell: ({ row }) => `${row.original.resident_name} (${row.original.resident_type})`,
      },
      { id: "amount", header: "Amount Due", cell: ({ row }) => formatCurrency(row.original.amount_due) },
      {
        id: "status",
        header: "Status",
        cell: ({ row }) => <ReportStatusBadge status={row.original.status} />,
      },
      {
        id: "payment_date",
        header: "Payment Date",
        cell: ({ row }) => (row.original.payment_date ? format(new Date(row.original.payment_date), "PP") : "—"),
      },
      { id: "payment_mode", header: "Mode", cell: ({ row }) => row.original.payment_mode ?? "—" },
      { id: "receipt_number", header: "Receipt #", cell: ({ row }) => row.original.receipt_number ?? "—" },
    ],
    []
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Select value={activeCycleId} onValueChange={setSelectedCycleId}>
          <SelectTrigger className="w-64">
            <SelectValue placeholder="Select a billing cycle" />
          </SelectTrigger>
          <SelectContent>
            {cycles.map((cycle) => (
              <SelectItem key={cycle.id} value={cycle.id}>
                {MONTH_NAMES[cycle.month - 1]} {cycle.year}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <ExportButtons
          towerId={towerId}
          reportType="collection"
          params={{ billing_cycle_id: activeCycleId }}
          disabled={!activeCycleId}
        />
      </div>

      {reportQuery.data && items.length > 0 ? (
        <div className="flex flex-wrap gap-3 text-sm">
          <div className="rounded-md border border-border bg-card px-3 py-1.5">
            <span className="text-muted-foreground">Total due:</span>{" "}
            <span className="font-medium text-foreground">{formatCurrency(reportQuery.data.totals.total_due)}</span>
          </div>
          <div className="rounded-md border border-border bg-card px-3 py-1.5">
            <span className="text-muted-foreground">Paid:</span>{" "}
            <span className="font-medium text-foreground">{formatCurrency(reportQuery.data.totals.total_paid)}</span>
          </div>
          <div className="rounded-md border border-border bg-card px-3 py-1.5">
            <span className="text-muted-foreground">Pending:</span>{" "}
            <span className="font-medium text-foreground">
              {formatCurrency(reportQuery.data.totals.total_pending)}
            </span>
          </div>
          <div className="rounded-md border border-border bg-card px-3 py-1.5">
            <span className="text-muted-foreground">Overdue:</span>{" "}
            <span className="font-medium text-foreground">
              {formatCurrency(reportQuery.data.totals.total_overdue)}
            </span>
          </div>
        </div>
      ) : null}

      {reportQuery.data && items.length === 0 ? (
        <ReportEmptyState message="No dues for this billing cycle yet." />
      ) : (
        <DataTable
          columns={columns}
          data={items}
          isLoading={reportQuery.isLoading || !activeCycleId}
          emptyMessage="No dues for this billing cycle yet."
        />
      )}
    </div>
  );
}
