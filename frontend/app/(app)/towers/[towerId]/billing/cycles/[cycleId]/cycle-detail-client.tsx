"use client";

import { useSearchParams } from "next/navigation";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { BillingStatCards } from "@/components/billing/BillingStatCards";
import { DuesDataTable } from "@/components/billing/dues-data-table";
import { useBillingCycle } from "@/hooks/use-billing-cycles";
import { useBillingDashboardStats, useCycleDues } from "@/hooks/use-dues";
import type { MaintenanceDueStatus } from "@/lib/api/types";

const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

const CYCLE_DUES_STATUS_OPTIONS = [
  { value: "all", label: "All" },
  { value: "pending", label: "Pending" },
  { value: "paid", label: "Paid" },
  { value: "overdue", label: "Overdue" },
];

/** /towers/[towerId]/billing/cycles/[cycleId] — frontend.md §2.4. */
export function CycleDetailClient({ towerId, cycleId }: { towerId: string; cycleId: string }) {
  const cycleQuery = useBillingCycle(towerId, cycleId);
  const statsQuery = useBillingDashboardStats(towerId, cycleId);
  const searchParams = useSearchParams();
  const status = (searchParams.get("status") ?? "all") as MaintenanceDueStatus | "all";
  const duesQuery = useCycleDues(towerId, cycleId, status);

  const cycle = cycleQuery.data;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          {cycleQuery.isLoading ? (
            <Skeleton className="h-6 w-64" />
          ) : cycle ? (
            <>
              <CardTitle>
                {MONTH_NAMES[cycle.month - 1]} {cycle.year}
              </CardTitle>
              <CardDescription className="space-y-1">
                <span className="block">Due date: {cycle.due_date}</span>
                {cycle.formula_snapshot ? (
                  <span className="block">
                    Formula used: Base ₹{cycle.formula_snapshot.base_amount} + ₹
                    {cycle.formula_snapshot.per_sqft_rate}/sq.ft., effective from{" "}
                    {cycle.formula_snapshot.effective_from}
                  </span>
                ) : null}
                <span className="block">Grace period used: {cycle.grace_period_days_snapshot} days</span>
              </CardDescription>
            </>
          ) : null}
        </CardHeader>
      </Card>

      <BillingStatCards
        totalCollected={cycle?.total_collected ?? 0}
        pendingCount={cycle?.pending_count ?? 0}
        overdueAmount={statsQuery.data?.overdue_amount ?? 0}
      />

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Dues</CardTitle>
        </CardHeader>
        <CardContent>
          <DuesDataTable
            towerId={towerId}
            statusOptions={CYCLE_DUES_STATUS_OPTIONS}
            dues={duesQuery.data}
            isLoading={duesQuery.isLoading}
          />
        </CardContent>
      </Card>
    </div>
  );
}
