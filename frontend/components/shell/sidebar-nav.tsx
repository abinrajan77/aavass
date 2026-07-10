"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import { useSession } from "@/components/providers/session-provider";
import { TOWER_NAV_ITEMS } from "./nav-config";
import { cn } from "@/lib/utils";

/**
 * Tower-scoped primary nav. Items are filtered by `session.permissions` —
 * NEVER a hardcoded role-name check — per
 * specs/01-auth-rbac-tower-setup/frontend.md "What must NOT break": a future
 * custom role with a subset of Admin's permissions must still see the
 * correct partial nav.
 *
 * Active item gets a `border-l-2 border-accent` gold bar, per the "Theme
 * application" section — the only place gold appears outside status badges
 * and primary CTAs.
 */
export function SidebarNav({ towerId }: { towerId: string }) {
  const session = useSession();
  const pathname = usePathname();

  const items = TOWER_NAV_ITEMS.filter(
    (item) => !item.permission || session?.permissions.includes(item.permission)
  );

  return (
    <SidebarGroup>
      <SidebarGroupLabel className="text-sidebar-foreground/60">Tower</SidebarGroupLabel>
      <SidebarMenu>
        {items.map((item) => {
          const href = item.href(towerId);
          const isActive = pathname === href;
          return (
            <SidebarMenuItem key={href}>
              <SidebarMenuButton
                asChild
                isActive={isActive}
                className={cn(
                  "border-l-2 border-transparent text-sidebar-foreground hover:bg-sidebar-accent/10 hover:text-sidebar-foreground",
                  isActive && "border-l-2 border-sidebar-accent bg-sidebar-accent/10 font-medium"
                )}
              >
                <Link href={href}>
                  <item.icon />
                  <span>{item.label}</span>
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>
          );
        })}
      </SidebarMenu>
    </SidebarGroup>
  );
}
