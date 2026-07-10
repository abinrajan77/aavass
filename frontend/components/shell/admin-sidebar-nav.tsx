"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Building2 } from "lucide-react";
import {
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import { cn } from "@/lib/utils";

/** Superuser-only nav (`/admin/*`) — gated at the route level by middleware.ts (`is_superuser`). */
export function AdminSidebarNav() {
  const pathname = usePathname();
  const isActive = pathname.startsWith("/admin/complexes");

  return (
    <SidebarGroup>
      <SidebarGroupLabel className="text-sidebar-foreground/60">Platform</SidebarGroupLabel>
      <SidebarMenu>
        <SidebarMenuItem>
          <SidebarMenuButton
            asChild
            isActive={isActive}
            className={cn(
              "border-l-2 border-transparent text-sidebar-foreground hover:bg-sidebar-accent/10 hover:text-sidebar-foreground",
              isActive && "border-l-2 border-sidebar-accent bg-sidebar-accent/10 font-medium"
            )}
          >
            <Link href="/admin/complexes">
              <Building2 />
              <span>Complexes</span>
            </Link>
          </SidebarMenuButton>
        </SidebarMenuItem>
      </SidebarMenu>
    </SidebarGroup>
  );
}
