"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Home } from "lucide-react";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Button } from "@/components/ui/button";
import { OccupancyStatusBadge } from "@/components/status-badge";
import { useOwnedFlatsSummary } from "@/hooks/use-owner-portal";

/**
 * ⌘K / Ctrl+K flat switcher for the owner portal — the structural template
 * is `components/shell/tower-switcher.tsx`, per
 * specs/05-reporting-owner-portal-notifications/frontend.md §4, but this
 * switches FLATS grouped by tower rather than towers: `session.towers` (used
 * by `TowerSwitcher`) carries no flat data, so this reads
 * `GET /api/v1/owners/me/flats-summary` instead (see
 * `hooks/use-owner-portal.ts`).
 *
 * Renders its own visible trigger button (not just the keyboard shortcut)
 * so it works as the "persistent header control on every /my-flats/* page"
 * frontend.md §4 requires — `app/(app)/my-flats/layout.tsx` renders this in
 * its header, covering the landing page, the dashboard, and the existing
 * Module 2 `/my-flats/[flatId]` edit page alike.
 *
 * Navigating via `router.push` to a fresh `/my-flats/[flatId]/dashboard`
 * route remounts the whole flat-scoped subtree (a fresh
 * `ownerPortalKeys.dashboard(flatId)` TanStack Query cache key per flat), so
 * no stale data from the previously-viewed flat/tower is ever shown
 * mid-transition — the "owner with flats in 3 towers switches context" edge
 * case in overview.md.
 */
export function FlatSwitcher() {
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const flatsQuery = useOwnedFlatsSummary();

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "k" && (event.metaKey || event.ctrlKey)) {
        event.preventDefault();
        setOpen((prev) => !prev);
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  const towers = flatsQuery.data?.towers ?? [];
  const totalFlats = towers.reduce((sum, t) => sum + t.flats.length, 0);

  // Fewer than 2 flats total -> no switcher friction, matching TowerSwitcher's
  // own "< 2 -> null" rule and frontend.md §4's single-flat auto-redirect.
  if (totalFlats < 2) {
    return null;
  }

  return (
    <>
      <Button variant="outline" size="sm" onClick={() => setOpen(true)}>
        <Home className="mr-2 h-4 w-4" />
        Switch flat
        <kbd className="ml-2 rounded bg-muted px-1 text-[10px] text-muted-foreground">⌘K</kbd>
      </Button>
      <CommandDialog open={open} onOpenChange={setOpen}>
        <CommandInput placeholder="Switch flat..." />
        <CommandList>
          <CommandEmpty>No flats found.</CommandEmpty>
          {towers.map((tower) => (
            <CommandGroup key={tower.tower_id} heading={tower.tower_name}>
              {tower.flats.map((flat) => (
                <CommandItem
                  key={flat.flat_id}
                  value={`${tower.tower_name} ${flat.flat_number}`}
                  onSelect={() => {
                    setOpen(false);
                    router.push(`/my-flats/${flat.flat_id}/dashboard`);
                  }}
                >
                  <Home className="mr-2 h-4 w-4" />
                  <span>Flat {flat.flat_number}</span>
                  <span className="ml-auto">
                    <OccupancyStatusBadge status={flat.occupancy_status} />
                  </span>
                </CommandItem>
              ))}
            </CommandGroup>
          ))}
        </CommandList>
      </CommandDialog>
    </>
  );
}
