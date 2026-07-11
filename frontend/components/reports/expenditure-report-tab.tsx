"use client";

import { useMemo, useState } from "react";
import { ColumnDef } from "@tanstack/react-table";
import { format, startOfMonth } from "date-fns";
import type { DateRange } from "react-day-picker";
import { DataTable } from "@/components/data-table/data-table";
import { DateRangePicker } from "@/components/form/date-range-picker";
import { Badge } from "@/components/ui/badge";
import { ExportButtons } from "./export-buttons";
import { ReportEmptyState } from "./report-empty-state";
import { useExpenditureReport } from "@/hooks/use-reports";
import { formatCurrency } from "@/lib/utils";
import type { ExpenditureReportRow } from "@/lib/api/types";

const CATEGORY_LABEL: Record<string, string> = {
  cleaning: "Cleaning",
  security: "Security",
  repairs: "Repairs",
  utilities: "Utilities",
  other: "Other",
};

/**
 * Expenditure Report — specs/05-reporting-owner-portal-notifications/
 * frontend.md §2: `Calendar` range picker (`period_start`/`period_end`),
 * required by backend.md §2.3. Defaults to the current calendar month so the
 * preview isn't empty on first load.
 */
export function ExpenditureReportTab({ towerId }: { towerId: string }) {
  const [range, setRange] = useState<DateRange | undefined>({ from: startOfMonth(new Date()), to: new Date() });
  const periodStart = range?.from ? format(range.from, "yyyy-MM-dd") : undefined;
  const periodEnd = range?.to ? format(range.to, "yyyy-MM-dd") : undefined;
  const reportQuery = useExpenditureReport(towerId, periodStart, periodEnd);
  const items = reportQuery.data?.items ?? [];

  const columns: ColumnDef<ExpenditureReportRow>[] = useMemo(
    () => [
      { id: "date", header: "Date", cell: ({ row }) => format(new Date(row.original.date), "PP") },
      {
        id: "category",
        header: "Category",
        cell: ({ row }) => <Badge variant="secondary">{CATEGORY_LABEL[row.original.category] ?? row.original.category}</Badge>,
      },
      { accessorKey: "description", header: "Description" },
      { accessorKey: "vendor_payee", header: "Vendor/Payee" },
      { id: "amount", header: "Amount", cell: ({ row }) => formatCurrency(row.original.amount) },
      { accessorKey: "payment_mode", header: "Mode" },
      {
        id: "has_attachment",
        header: "Attachment",
        cell: ({ row }) => (row.original.has_attachment ? "Yes" : "—"),
      },
    ],
    []
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <DateRangePicker value={range} onChange={setRange} placeholder="Select a period" />
        <ExportButtons
          towerId={towerId}
          reportType="expenditure"
          params={{ period_start: periodStart, period_end: periodEnd }}
          disabled={!periodStart || !periodEnd}
        />
      </div>

      {reportQuery.data ? (
        <div className="flex flex-wrap gap-3 text-sm" data-testid="expenditure-category-totals">
          {reportQuery.data.category_totals.map((c) => (
            <div key={c.category} className="rounded-md border border-border bg-card px-3 py-1.5">
              <span className="text-muted-foreground">{CATEGORY_LABEL[c.category] ?? c.category}:</span>{" "}
              <span className="font-medium text-foreground">{formatCurrency(c.total)}</span>
            </div>
          ))}
          <div className="rounded-md border border-border bg-card px-3 py-1.5 font-medium text-foreground">
            Grand total: {formatCurrency(reportQuery.data.grand_total)}
          </div>
        </div>
      ) : null}

      {reportQuery.data && items.length === 0 ? (
        <ReportEmptyState message="No expenditures recorded for this period." />
      ) : (
        <DataTable
          columns={columns}
          data={items}
          isLoading={reportQuery.isLoading}
          emptyMessage="No expenditures recorded for this period."
        />
      )}
    </div>
  );
}
