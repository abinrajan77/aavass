"use client";

import { useMemo, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ExportButtons } from "./export-buttons";
import { ReportEmptyState } from "./report-empty-state";
import { useCollectionVsExpenditureReport } from "@/hooks/use-reports";
import { formatCurrency } from "@/lib/utils";
import type { ReportPeriodType } from "@/lib/api/types";

const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

/** Apr 1 - Mar 31, India convention, per backend.md §2.4. */
function currentFinancialYearStart(): number {
  const now = new Date();
  return now.getMonth() < 3 ? now.getFullYear() - 1 : now.getFullYear();
}

function yearOptions(centerYear: number): number[] {
  return Array.from({ length: 5 }, (_, i) => centerYear - 3 + i);
}

/**
 * Collection vs Expenditure Summary — specs/05-reporting-owner-portal-
 * notifications/frontend.md §2: `Select` for `period_type` (Month / Financial
 * Year) + a `Select` for month/year or FY.
 */
export function CollectionVsExpenditureTab({ towerId }: { towerId: string }) {
  const [periodType, setPeriodType] = useState<ReportPeriodType>("month");
  const [month, setMonth] = useState(new Date().getMonth() + 1);
  const [year, setYear] = useState(currentFinancialYearStart());

  const params = useMemo(
    () =>
      periodType === "month"
        ? { period_type: "month" as const, month, year }
        : { period_type: "financial_year" as const, year },
    [periodType, month, year]
  );

  const reportQuery = useCollectionVsExpenditureReport(towerId, params);
  const categoryTotals = reportQuery.data?.expenditure_by_category ?? [];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <Select value={periodType} onValueChange={(v) => setPeriodType(v as ReportPeriodType)}>
            <SelectTrigger className="w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="month">Month</SelectItem>
              <SelectItem value="financial_year">Financial Year</SelectItem>
            </SelectContent>
          </Select>

          {periodType === "month" ? (
            <Select value={String(month)} onValueChange={(v) => setMonth(Number(v))}>
              <SelectTrigger className="w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {MONTH_NAMES.map((name, idx) => (
                  <SelectItem key={name} value={String(idx + 1)}>
                    {name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : null}

          <Select value={String(year)} onValueChange={(v) => setYear(Number(v))}>
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {yearOptions(currentFinancialYearStart()).map((y) => (
                <SelectItem key={y} value={String(y)}>
                  {periodType === "financial_year" ? `FY ${y}-${String(y + 1).slice(-2)}` : y}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <ExportButtons towerId={towerId} reportType="collection_vs_expenditure" params={params} />
      </div>

      {reportQuery.data ? (
        <>
          <p className="text-sm text-muted-foreground">{reportQuery.data.period_label}</p>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <Card>
              <CardContent className="pt-6">
                <p className="text-sm text-muted-foreground">Total Collected</p>
                <p className="text-2xl font-semibold text-foreground">
                  {formatCurrency(reportQuery.data.total_collected)}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <p className="text-sm text-muted-foreground">Total Expenditure</p>
                <p className="text-2xl font-semibold text-foreground">
                  {formatCurrency(reportQuery.data.total_expenditure)}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <p className="text-sm text-muted-foreground">Net</p>
                <p className="text-2xl font-semibold text-foreground">{formatCurrency(reportQuery.data.net)}</p>
              </CardContent>
            </Card>
          </div>
        </>
      ) : null}

      {reportQuery.data && categoryTotals.length === 0 ? (
        <ReportEmptyState message="No expenditures recorded for this period." />
      ) : (
        <div className="flex flex-wrap gap-3 text-sm" data-testid="cve-category-totals">
          {categoryTotals.map((c) => (
            <div key={c.category} className="rounded-md border border-border bg-card px-3 py-1.5">
              <span className="text-muted-foreground">{c.category}:</span>{" "}
              <span className="font-medium text-foreground">{formatCurrency(c.total)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
