"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { format } from "date-fns";
import { ColumnDef } from "@tanstack/react-table";
import { useQuery } from "@tanstack/react-query";
import { Download, Pencil } from "lucide-react";
import { BentoGrid, BentoCard } from "@/components/magicui/bento-grid";
import { NumberTicker } from "@/components/magicui/number-ticker";
import { ShineBorder } from "@/components/magicui/shine-border";
import { DataTable } from "@/components/data-table/data-table";
import { ReportStatusBadge } from "@/components/reports/report-status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useOwnerFlatDashboard } from "@/hooks/use-owner-portal";
import { getExpenditureReport } from "@/lib/api/reports";
import { formatCurrency } from "@/lib/utils";
import type { CollectionReportRow, ExpenditureReportRow } from "@/lib/api/types";

const CATEGORY_LABEL: Record<string, string> = {
  cleaning: "Cleaning",
  security: "Security",
  repairs: "Repairs",
  utilities: "Utilities",
  other: "Other",
};

/**
 * `/my-flats/[flatId]/dashboard` — specs/05-reporting-owner-portal-
 * notifications/frontend.md §5, `BentoGrid` layout per that section exactly.
 */
export function FlatDashboardClient({ flatId }: { flatId: string }) {
  const dashboardQuery = useOwnerFlatDashboard(flatId);
  const [selectedDue, setSelectedDue] = useState<CollectionReportRow | null>(null);
  const [expenditurePeriod, setExpenditurePeriod] = useState<"current_fy" | "all_time">("current_fy");

  const data = dashboardQuery.data;

  // "Current FY by default with a period Select to widen" (frontend.md §5) —
  // the dashboard response's own `tower_expenditures` is already scoped to
  // the current FY (backend.md §3.2); widening re-fetches via the same
  // report endpoint Module 5's admin Expenditure report tab uses, over a
  // deliberately wide window, rather than inventing a second aggregate.
  const widenedExpendituresQuery = useQuery({
    queryKey: ["owner-dashboard-all-time-expenditures", data?.tower_id],
    queryFn: () => getExpenditureReport(data!.tower_id, "2000-01-01", format(new Date(), "yyyy-MM-dd")),
    enabled: expenditurePeriod === "all_time" && Boolean(data?.tower_id),
  });

  const expenditureRows: ExpenditureReportRow[] =
    expenditurePeriod === "all_time"
      ? widenedExpendituresQuery.data?.items ?? []
      : data?.tower_expenditures ?? [];

  const paymentColumns: ColumnDef<CollectionReportRow>[] = useMemo(
    () => [
      {
        id: "period",
        header: "Period",
        cell: ({ row }) => (row.original.payment_date ? format(new Date(row.original.payment_date), "MMM yyyy") : "—"),
      },
      { id: "amount", header: "Amount", cell: ({ row }) => formatCurrency(row.original.amount_due) },
      {
        id: "status",
        header: "Status",
        cell: ({ row }) => <ReportStatusBadge status={row.original.status} />,
      },
    ],
    []
  );

  const expenditureColumns: ColumnDef<ExpenditureReportRow>[] = useMemo(
    () => [
      { id: "date", header: "Date", cell: ({ row }) => format(new Date(row.original.date), "PP") },
      {
        id: "category",
        header: "Category",
        cell: ({ row }) => <Badge variant="secondary">{CATEGORY_LABEL[row.original.category] ?? row.original.category}</Badge>,
      },
      { accessorKey: "description", header: "Description" },
      { id: "amount", header: "Amount", cell: ({ row }) => formatCurrency(row.original.amount) },
    ],
    []
  );

  if (dashboardQuery.isLoading || !data) {
    return (
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Skeleton className="h-40 sm:col-span-3" />
        <Skeleton className="h-32" />
        <Skeleton className="h-32" />
        <Skeleton className="h-32" />
      </div>
    );
  }

  const currentDue = data.current_due;
  const isOverdue = currentDue?.status === "overdue";
  const currentTenants = data.tenant_history.filter((t) => t.is_current);
  const pastTenants = data.tenant_history.filter((t) => !t.is_current);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-lg font-semibold text-foreground">Flat {data.flat_number}</h1>
        <Button variant="outline" size="sm" asChild>
          <Link href={`/my-flats/${flatId}`}>
            <Pencil className="mr-2 h-4 w-4" />
            Edit contact / tenant / occupancy
          </Link>
        </Button>
      </div>

      <BentoGrid>
        {/* Large cell — current due status */}
        <BentoCard className={isOverdue ? "relative overflow-hidden sm:col-span-2" : "sm:col-span-2"}>
          {isOverdue ? <ShineBorder /> : null}
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">Current cycle due</p>
            {currentDue ? (
              <>
                <div className="flex items-center gap-3">
                  <span className="text-3xl font-semibold text-foreground">
                    {formatCurrency(currentDue.amount_due)}
                  </span>
                  <ReportStatusBadge status={currentDue.status} />
                </div>
                <p className="text-sm text-muted-foreground">
                  {currentDue.payment_date
                    ? `Paid on ${format(new Date(currentDue.payment_date), "PP")}`
                    : "Not yet paid"}
                </p>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">No due generated for the current cycle yet.</p>
            )}
          </div>
        </BentoCard>

        {/* Stat cells — YTD totals */}
        <BentoCard>
          <p className="text-sm text-muted-foreground">Total Paid YTD</p>
          <NumberTicker
            value={data.ytd_totals.total_paid_ytd}
            className="text-2xl font-semibold text-foreground"
            decimalPlaces={2}
            prefix="₹"
          />
        </BentoCard>

        <BentoCard>
          <p className="text-sm text-muted-foreground">Total Due YTD</p>
          <NumberTicker
            value={data.ytd_totals.total_due_ytd}
            className="text-2xl font-semibold text-foreground"
            decimalPlaces={2}
            prefix="₹"
          />
        </BentoCard>

        {/* Payment history */}
        <BentoCard className="sm:col-span-2">
          <CardTitleRow title="Payment history" />
          <DataTable
            columns={paymentColumns}
            data={data.payment_history}
            emptyMessage="No payment history yet."
            onRowClick={(row) => setSelectedDue(row)}
          />
        </BentoCard>

        {/* Receipts */}
        <BentoCard>
          <CardTitleRow title="Receipts" />
          {data.receipts.length === 0 ? (
            <p className="text-sm text-muted-foreground">No receipts yet.</p>
          ) : (
            <ul className="space-y-2">
              {data.receipts.map((receipt) => (
                <li key={receipt.receipt_id} className="flex items-center justify-between text-sm">
                  <span>
                    {receipt.receipt_number} · {receipt.billing_period}
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => window.open(receipt.download_url, "_blank", "noopener,noreferrer")}
                  >
                    <Download className="h-4 w-4" />
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </BentoCard>

        {/* Tower expenditures */}
        <BentoCard className="sm:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <CardTitleRow title="Tower expenditures" />
            <Select value={expenditurePeriod} onValueChange={(v) => setExpenditurePeriod(v as typeof expenditurePeriod)}>
              <SelectTrigger className="w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="current_fy">Current FY</SelectItem>
                <SelectItem value="all_time">All recorded</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <DataTable
            columns={expenditureColumns}
            data={expenditureRows}
            isLoading={expenditurePeriod === "all_time" && widenedExpendituresQuery.isLoading}
            emptyMessage="No expenditures recorded for this tower yet."
          />
        </BentoCard>

        {/* Tenant history */}
        <BentoCard>
          <CardTitleRow title="Tenant history" />
          <Tabs defaultValue="current">
            <TabsList>
              <TabsTrigger value="current">Current</TabsTrigger>
              <TabsTrigger value="past">Past</TabsTrigger>
            </TabsList>
            <TabsContent value="current" className="space-y-2">
              {currentTenants.length === 0 ? (
                <p className="text-sm text-muted-foreground">No current tenant — owner-occupied.</p>
              ) : (
                currentTenants.map((tenant, idx) => <TenantRow key={idx} tenant={tenant} />)
              )}
            </TabsContent>
            <TabsContent value="past" className="space-y-2">
              {pastTenants.length === 0 ? (
                <p className="text-sm text-muted-foreground">No tenant history for this flat.</p>
              ) : (
                pastTenants.map((tenant, idx) => <TenantRow key={idx} tenant={tenant} />)
              )}
            </TabsContent>
          </Tabs>
        </BentoCard>
      </BentoGrid>

      <Sheet open={Boolean(selectedDue)} onOpenChange={(open) => !open && setSelectedDue(null)}>
        <SheetContent>
          <SheetHeader>
            <SheetTitle>Due detail</SheetTitle>
            <SheetDescription>Flat {data.flat_number}</SheetDescription>
          </SheetHeader>
          {selectedDue
            ? (() => {
                const matchingReceipt = data.receipts.find(
                  (r) => r.receipt_number === selectedDue.receipt_number
                );
                return (
                  <div className="mt-4 space-y-3 text-sm">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Amount</span>
                      <span className="text-foreground">{formatCurrency(selectedDue.amount_due)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Status</span>
                      <ReportStatusBadge status={selectedDue.status} />
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Payment date</span>
                      <span className="text-foreground">
                        {selectedDue.payment_date ? format(new Date(selectedDue.payment_date), "PP") : "—"}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Payment mode</span>
                      <span className="text-foreground">{selectedDue.payment_mode ?? "—"}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Receipt #</span>
                      <span className="text-foreground">{selectedDue.receipt_number ?? "—"}</span>
                    </div>
                    {matchingReceipt ? (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() =>
                          window.open(matchingReceipt.download_url, "_blank", "noopener,noreferrer")
                        }
                      >
                        <Download className="mr-2 h-4 w-4" />
                        Download receipt
                      </Button>
                    ) : null}
                  </div>
                );
              })()
            : null}
        </SheetContent>
      </Sheet>
    </div>
  );
}

function CardTitleRow({ title }: { title: string }) {
  return (
    <CardHeader className="p-0 pb-3">
      <CardTitle className="text-base">{title}</CardTitle>
    </CardHeader>
  );
}

function TenantRow({ tenant }: { tenant: { tenant_name: string; phone_number: string; lease_start: string; lease_end: string | null } }) {
  return (
    <div className="rounded-md border border-border p-2 text-sm">
      <p className="font-medium text-foreground">{tenant.tenant_name}</p>
      <p className="text-muted-foreground">{tenant.phone_number}</p>
      <p className="text-xs text-muted-foreground">
        {format(new Date(tenant.lease_start), "PP")} –{" "}
        {tenant.lease_end ? format(new Date(tenant.lease_end), "PP") : "present"}
      </p>
    </div>
  );
}
