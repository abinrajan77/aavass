import Link from "next/link";
import { FlatSwitcher } from "@/components/shell/flat-switcher";
import { UserMenu } from "@/components/shell/user-menu";

/**
 * Shared header for every `/my-flats/*` page (landing, per-flat dashboard,
 * and Module 2's existing `/my-flats/[flatId]` edit page alike) —
 * specs/05-reporting-owner-portal-notifications/frontend.md §4: "The Command
 * palette is also reachable from a persistent header control on every
 * `/my-flats/*` page (not just the landing) so switching context doesn't
 * require returning to `/my-flats` first."
 *
 * Deliberately lighter than `components/shell/app-shell.tsx` (no Sidebar) —
 * the owner portal has no tower-admin nav items (`TOWER_NAV_ITEMS` doesn't
 * apply to a flat_owner account), just this header plus whatever the page
 * itself renders.
 */
export default function MyFlatsLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <header className="flex h-14 items-center justify-between gap-2 border-b border-border bg-background px-4">
        <Link href="/my-flats" className="flex items-center gap-2 text-sm font-semibold tracking-wide text-foreground">
          <span className="inline-block h-2 w-2 rounded-full bg-accent" />
          Aavaas — My Flats
        </Link>
        <div className="flex items-center gap-2">
          <FlatSwitcher />
          <UserMenu />
        </div>
      </header>
      <main className="flex-1 p-6">{children}</main>
    </div>
  );
}
