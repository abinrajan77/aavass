"use client";

import Link from "next/link";
import { formatDistanceToNow } from "date-fns";
import { Building2, CalendarClock, KeyRound, Receipt, ShieldAlert } from "lucide-react";
import { BentoCard, BentoGrid } from "@/components/magicui/bento-grid";
import { AnimatedList } from "@/components/magicui/animated-list";
import { NumberTicker } from "@/components/magicui/number-ticker";
import { ShineBorder } from "@/components/magicui/shine-border";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useSession } from "@/components/providers/session-provider";
import { useRecentActivity, useTowerDashboardStats } from "@/hooks/use-dashboard";
import { hasPermission, PERMISSIONS } from "@/lib/permissions";
import { formatCurrency } from "@/lib/utils";

/** Same permission gate each nav-config.ts item uses for the same destination — a quick
 * link must never be visible to a session that can't actually reach the page it points to. */
const QUICK_LINKS = [
  { label: "Flats", icon: KeyRound, path: "flats", permission: PERMISSIONS.VIEW_TOWER_DATA },
  { label: "Billing Cycles", icon: CalendarClock, path: "billing/cycles", permission: PERMISSIONS.VIEW_TOWER_DATA },
  { label: "Special Collections", icon: ShieldAlert, path: "special-collections", permission: PERMISSIONS.VIEW_TOWER_DATA },
  { label: "Expenditures", icon: Receipt, path: "expenditures", permission: PERMISSIONS.VIEW_TOWER_DATA },
  { label: "Tower Profile", icon: Building2, path: "settings/tower-profile", permission: PERMISSIONS.MANAGE_COMPLEX },
] as const;

/**
 * `/towers/[towerId]` dashboard body — specs/00-architecture-and-standards.md §3.2's
 * BentoGrid stat-card set (previously an unclaimed placeholder: neither Module 1's scaffold
 * nor Module 5's actual spec ever built this screen, despite both referencing it).
 */
export function TowerDashboardClient({ towerId }: { towerId: string }) {
  const session = useSession();
  const statsQuery = useTowerDashboardStats(towerId);
  const activityQuery = useRecentActivity(towerId);
  const stats = statsQuery.data;

  const overdueCount = stats ? Number(stats.overdue_dues_count) : 0;
  const visibleQuickLinks = QUICK_LINKS.filter((link) => hasPermission(session, link.permission));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold text-foreground">Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          Collection, dues, and activity at a glance for this tower.
        </p>
      </div>

      <BentoGrid>
        <BentoCard className="sm:col-span-2">
          <p className="text-sm text-muted-foreground">Collected this month</p>
          {statsQuery.isLoading ? (
            <Skeleton className="mt-2 h-9 w-40" />
          ) : (
            <NumberTicker
              className="mt-2 block text-3xl font-bold text-foreground"
              value={Number(stats?.total_collected_this_month ?? 0)}
              prefix="₹"
              decimalPlaces={2}
            />
          )}
        </BentoCard>

        <BentoCard>
          <p className="text-sm text-muted-foreground">Pending dues</p>
          {statsQuery.isLoading ? (
            <Skeleton className="mt-2 h-9 w-16" />
          ) : (
            <NumberTicker
              className="mt-2 block text-3xl font-bold text-foreground"
              value={Number(stats?.pending_dues_count ?? 0)}
            />
          )}
        </BentoCard>

        <BentoCard className="relative overflow-hidden">
          {!statsQuery.isLoading && overdueCount > 0 ? <ShineBorder /> : null}
          <p className="text-sm text-muted-foreground">Overdue</p>
          {statsQuery.isLoading ? (
            <Skeleton className="mt-2 h-9 w-32" />
          ) : (
            <>
              <NumberTicker
                className="mt-2 block text-3xl font-bold text-destructive"
                value={overdueCount}
              />
              <p className="mt-1 text-sm text-muted-foreground">
                {formatCurrency(Number(stats?.overdue_amount ?? 0))} outstanding
              </p>
            </>
          )}
        </BentoCard>

        <BentoCard>
          <p className="text-sm text-muted-foreground">Occupancy</p>
          {statsQuery.isLoading ? (
            <Skeleton className="mt-2 h-9 w-24" />
          ) : (
            <p className="mt-2 text-3xl font-bold text-foreground">
              {stats?.occupied_flats}
              <span className="text-lg font-normal text-muted-foreground">
                {" "}
                / {stats?.total_flats} flats
              </span>
            </p>
          )}
        </BentoCard>

        <BentoCard>
          <p className="text-sm text-muted-foreground">Open special collections</p>
          {statsQuery.isLoading ? (
            <Skeleton className="mt-2 h-9 w-16" />
          ) : (
            <NumberTicker
              className="mt-2 block text-3xl font-bold text-foreground"
              value={Number(stats?.open_special_collections_count ?? 0)}
            />
          )}
        </BentoCard>

        <BentoCard>
          <p className="text-sm text-muted-foreground">Expenditure this month</p>
          {statsQuery.isLoading ? (
            <Skeleton className="mt-2 h-9 w-32" />
          ) : (
            <NumberTicker
              className="mt-2 block text-3xl font-bold text-foreground"
              value={Number(stats?.expenditure_this_month ?? 0)}
              prefix="₹"
              decimalPlaces={2}
            />
          )}
        </BentoCard>
      </BentoGrid>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="rounded-xl border border-border bg-card p-6 shadow-sm lg:col-span-1">
          <h2 className="mb-3 text-sm font-medium text-foreground">Quick links</h2>
          <div className="flex flex-col gap-2 text-sm">
            {visibleQuickLinks.map((link) => (
              <Link
                key={link.path}
                href={`/towers/${towerId}/${link.path}`}
                className="flex items-center gap-2 text-primary hover:underline"
              >
                <link.icon className="h-4 w-4" /> {link.label}
              </Link>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-border bg-card p-6 shadow-sm lg:col-span-2">
          <h2 className="mb-3 text-sm font-medium text-foreground">Recent activity</h2>
          {activityQuery.isLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : activityQuery.data && activityQuery.data.items.length > 0 ? (
            <AnimatedList>
              {activityQuery.data.items.map((entry) => (
                <div
                  key={entry.id}
                  className="flex items-center justify-between gap-3 rounded-md border border-border/60 bg-background px-3 py-2"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm text-foreground">
                      <span className="font-medium">{entry.actor_label}</span>{" "}
                      <span className="text-muted-foreground">
                        {entry.action.toLowerCase().replaceAll("_", " ")}
                      </span>
                    </p>
                    <p className="text-xs text-muted-foreground">{entry.entity_type}</p>
                  </div>
                  <Badge variant="mutedOutline" className="shrink-0">
                    {formatDistanceToNow(new Date(entry.created_at), { addSuffix: true })}
                  </Badge>
                </div>
              ))}
            </AnimatedList>
          ) : (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No recent activity for this tower yet.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
