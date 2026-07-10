"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { DuesDataTable } from "@/components/billing/dues-data-table";
import { useBillingCycles } from "@/hooks/use-billing-cycles";
import { useTowerDues } from "@/hooks/use-dues";

const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

// Cross-cycle route documents `status=pending|overdue` only (backend.md
// §6.4) — matching PRD §6.3.4's "pending/overdue at a glance" framing, this
// page omits a "Paid" tab (see hooks/use-dues.ts useTowerDues doc comment).
const TOWER_DUES_STATUS_OPTIONS = [
  { value: "all", label: "All" },
  { value: "pending", label: "Pending" },
  { value: "overdue", label: "Overdue" },
];

/** /towers/[towerId]/billing/dues — frontend.md §2.5. */
export function DuesClient({ towerId }: { towerId: string }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const status = (searchParams.get("status") ?? "all") as "pending" | "overdue" | "all";
  const cycleId = searchParams.get("cycle_id") ?? undefined;

  const cyclesQuery = useBillingCycles(towerId);
  const duesQuery = useTowerDues(towerId, status, cycleId);

  function handleCycleChange(value: string) {
    const params = new URLSearchParams(searchParams.toString());
    if (value === "all") {
      params.delete("cycle_id");
    } else {
      params.set("cycle_id", value);
    }
    const query = params.toString();
    router.replace(query ? `${pathname}?${query}` : pathname);
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold text-foreground">Dues</h1>
          <CardDescription>
            Cross-cycle pending/overdue dues at a glance — drill in from here without opening a specific cycle
            first.
          </CardDescription>
        </div>
        <Select value={cycleId ?? "all"} onValueChange={handleCycleChange}>
          <SelectTrigger className="w-56">
            <SelectValue placeholder="All Cycles" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Cycles</SelectItem>
            {cyclesQuery.data?.items.map((cycle) => (
              <SelectItem key={cycle.id} value={cycle.id}>
                {MONTH_NAMES[cycle.month - 1]} {cycle.year}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">All flats</CardTitle>
        </CardHeader>
        <CardContent>
          <DuesDataTable
            towerId={towerId}
            statusOptions={TOWER_DUES_STATUS_OPTIONS}
            dues={duesQuery.data}
            isLoading={duesQuery.isLoading}
          />
        </CardContent>
      </Card>
    </div>
  );
}
