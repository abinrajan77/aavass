"use client";

import Link from "next/link";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { BreadcrumbNav } from "./breadcrumb-nav";
import { TowerSwitcher } from "./tower-switcher";
import { UserMenu } from "./user-menu";

/**
 * Shared authenticated app shell — specs/01-auth-rbac-tower-setup/frontend.md
 * "Shared app shell" + "Theme application": Sidebar uses bg-primary /
 * text-primary-foreground (mapped via the `sidebar-*` CSS variables), active
 * nav item gets a gold `border-l-2 border-accent` bar (see SidebarNav).
 * Used by every authenticated route.
 *
 * `nav` is injected by the caller (tower-scoped `<SidebarNav>` vs the
 * superuser-only admin nav) so this component stays agnostic of which
 * section of the app it's rendering.
 */
export function AppShell({ nav, children }: { nav?: React.ReactNode; children: React.ReactNode }) {
  return (
    <SidebarProvider>
      <Sidebar className="border-sidebar-border bg-sidebar text-sidebar-foreground">
        <SidebarHeader className="px-3 py-3">
          <Link href="/" className="flex items-center gap-2 px-1 text-sm font-semibold tracking-wide">
            <span className="inline-block h-2 w-2 rounded-full bg-sidebar-accent" />
            Aavaas
          </Link>
        </SidebarHeader>
        <SidebarContent>{nav}</SidebarContent>
        <SidebarFooter className="px-3 py-3">
          <p className="px-1 text-[11px] text-sidebar-foreground/50">
            Press <kbd className="rounded bg-sidebar-accent/20 px-1">⌘K</kbd> to switch towers
          </p>
        </SidebarFooter>
      </Sidebar>
      <SidebarInset>
        <header className="flex h-14 items-center justify-between gap-2 border-b border-border bg-background px-4">
          <div className="flex items-center gap-2">
            <SidebarTrigger />
            <BreadcrumbNav />
          </div>
          <UserMenu />
        </header>
        <main className="flex-1 bg-background p-6">{children}</main>
        <TowerSwitcher />
      </SidebarInset>
    </SidebarProvider>
  );
}
