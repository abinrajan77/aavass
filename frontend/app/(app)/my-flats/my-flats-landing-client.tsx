"use client";

import { useEffect, useMemo } from "react";
import { useRouter } from "next/navigation";
import { Home } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { OccupancyStatusBadge, PaymentStatusBadge } from "@/components/status-badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useOwnedFlatsSummary } from "@/hooks/use-owner-portal";
import type { CurrentDueStatus } from "@/lib/api/types";

const DUE_STATUS_LABEL: Partial<Record<CurrentDueStatus, "Paid" | "Pending" | "Overdue">> = {
  paid: "Paid",
  pending: "Pending",
  overdue: "Overdue",
};

/**
 * `/my-flats` — owner-portal landing, specs/05-reporting-owner-portal-
 * notifications/frontend.md §4:
 *   - exactly one flat total (across however many towers, though in
 *     practice one flat implies one tower) -> redirect straight to that
 *     flat's dashboard, no picker friction.
 *   - multiple -> render a picker grouped by tower (the persistent header
 *     `FlatSwitcher`'s Command-palette is the *primary* switcher per the
 *     spec; this page's card grid is the equivalent non-modal landing view
 *     for the same data, reached before ⌘K is ever invoked).
 */
export function MyFlatsLandingClient() {
  const router = useRouter();
  const flatsQuery = useOwnedFlatsSummary();
  const towers = useMemo(() => flatsQuery.data?.towers ?? [], [flatsQuery.data]);
  const allFlats = useMemo(() => towers.flatMap((t) => t.flats), [towers]);

  useEffect(() => {
    if (allFlats.length === 1) {
      router.replace(`/my-flats/${allFlats[0].flat_id}/dashboard`);
    }
  }, [allFlats, router]);

  if (flatsQuery.isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  if (allFlats.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-border p-10 text-center text-sm text-muted-foreground">
        You don&apos;t currently own any active flats.
      </div>
    );
  }

  if (allFlats.length === 1) {
    // Redirect handled by the effect above — render a placeholder meanwhile
    // rather than a picker, since only one flat exists.
    return <Skeleton className="h-40 w-full" data-testid="my-flats-redirecting" />;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold text-foreground">Your flats</h1>
        <p className="text-sm text-muted-foreground">
          Choose a flat to view its dashboard, or press <kbd className="rounded bg-muted px-1">⌘K</kbd> any time to
          switch.
        </p>
      </div>
      {towers.map((tower) => (
        <div key={tower.tower_id} className="space-y-3">
          <h2 className="text-sm font-medium text-muted-foreground">{tower.tower_name}</h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {tower.flats.map((flat) => (
              <Card
                key={flat.flat_id}
                className="cursor-pointer transition-colors hover:border-primary"
                onClick={() => router.push(`/my-flats/${flat.flat_id}/dashboard`)}
              >
                <CardHeader className="flex-row items-center justify-between space-y-0">
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Home className="h-4 w-4 text-primary" />
                    Flat {flat.flat_number}
                  </CardTitle>
                  <OccupancyStatusBadge status={flat.occupancy_status} />
                </CardHeader>
                <CardContent className="flex items-center justify-between pt-0 text-sm text-muted-foreground">
                  <span>{flat.is_primary_owner ? "Primary owner" : "Co-owner"}</span>
                  {DUE_STATUS_LABEL[flat.current_due_status] ? (
                    <PaymentStatusBadge status={DUE_STATUS_LABEL[flat.current_due_status]!} />
                  ) : null}
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
