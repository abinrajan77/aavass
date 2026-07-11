"use client";

import { useMemo, useState } from "react";
import { ColumnDef } from "@tanstack/react-table";
import { format } from "date-fns";
import { DataTable } from "@/components/data-table/data-table";
import { DatePickerField } from "@/components/billing/date-picker-field";
import { ExportButtons } from "./export-buttons";
import { ReportEmptyState } from "./report-empty-state";
import { useOutstandingDuesReport } from "@/hooks/use-reports";
import { formatCurrency } from "@/lib/utils";
import type { OutstandingDueRow } from "@/lib/api/types";

/**
 * Outstanding Dues Report — specs/05-reporting-owner-portal-notifications/
 * frontend.md §2: `Calendar` + `Popover` for an optional "as of" date
 * (defaults to today, per backend.md §2.2's `as_of_date` default).
 */
export function OutstandingDuesReportTab({ towerId }: { towerId: string }) {
  const [asOfDate, setAsOfDate] = useState<Date | undefined>(undefined);
  const asOfParam = asOfDate ? format(asOfDate, "yyyy-MM-dd") : undefined;
  const reportQuery = useOutstandingDuesReport(towerId, asOfParam);
  const items = reportQuery.data?.items ?? [];

  const columns: ColumnDef<OutstandingDueRow>[] = useMemo(
    () => [
      { accessorKey: "flat_number", header: "Flat" },
      {
        id: "due_type",
        header: "Due Type",
        cell: ({ row }) => (row.original.due_type === "maintenance" ? "Maintenance" : "Special Collection"),
      },
      { id: "owners", header: "Owner(s)", cell: ({ row }) => row.original.owner_names.join(", ") || "—" },
      { accessorKey: "resident_name", header: "Resident" },
      { id: "amount", header: "Amount Due", cell: ({ row }) => formatCurrency(row.original.amount_due) },
      { id: "due_date", header: "Due Date", cell: ({ row }) => format(new Date(row.original.due_date), "PP") },
      { accessorKey: "days_overdue", header: "Days Overdue" },
    ],
    []
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <DatePickerField
          value={asOfDate}
          onChange={setAsOfDate}
          placeholder="As of today"
          ariaLabel="As-of date"
        />
        <ExportButtons towerId={towerId} reportType="outstanding_dues" params={{ as_of_date: asOfParam }} />
      </div>

      {reportQuery.data && items.length > 0 ? (
        <div className="rounded-md border border-border bg-card px-3 py-1.5 text-sm">
          <span className="text-muted-foreground">Total outstanding:</span>{" "}
          <span className="font-medium text-foreground">{formatCurrency(reportQuery.data.total_outstanding)}</span>
        </div>
      ) : null}

      {reportQuery.data && items.length === 0 ? (
        <ReportEmptyState message="No overdue dues as of this date." />
      ) : (
        <DataTable
          columns={columns}
          data={items}
          isLoading={reportQuery.isLoading}
          emptyMessage="No overdue dues as of this date."
        />
      )}
    </div>
  );
}
