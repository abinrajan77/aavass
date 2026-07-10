"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Building2 } from "lucide-react";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { useSession } from "@/components/providers/session-provider";

/**
 * ⌘K / Ctrl+K tower switcher — specs/01-auth-rbac-tower-setup/frontend.md
 * "Shared app shell": used only as a tower switcher in this module (no
 * general search palette, per overview.md non-goals).
 *
 * Navigating via `router.push` to a fresh `/towers/[towerId]` route causes
 * the whole tower-scoped subtree (server components + tower-keyed TanStack
 * queries) to remount/refetch, so no stale data from the previous tower is
 * ever shown mid-transition — see the frontend test plan's
 * "no stale data flashing" requirement.
 */
export function TowerSwitcher() {
  const [open, setOpen] = useState(false);
  const session = useSession();
  const router = useRouter();

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

  if (!session || session.towers.length < 2) {
    return null;
  }

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput placeholder="Switch tower..." />
      <CommandList>
        <CommandEmpty>No towers found.</CommandEmpty>
        <CommandGroup heading="Your towers">
          {session.towers.map((tower) => (
            <CommandItem
              key={tower.tower_id}
              value={tower.tower_name}
              onSelect={() => {
                setOpen(false);
                router.push(`/towers/${tower.tower_id}`);
              }}
            >
              <Building2 className="mr-2 h-4 w-4" />
              <span>{tower.tower_name}</span>
              <span className="ml-auto text-xs text-muted-foreground">{tower.role_name}</span>
            </CommandItem>
          ))}
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
