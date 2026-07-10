"use client";

import { useRouter } from "next/navigation";
import { LogOut, User as UserIcon } from "lucide-react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useSession } from "@/components/providers/session-provider";
import { logout } from "@/lib/api/auth";
import { toast } from "sonner";

function initials(nameOrEmail: string): string {
  const parts = nameOrEmail.split(/[\s@]+/).filter(Boolean);
  return parts.slice(0, 2).map((p) => p[0]?.toUpperCase()).join("") || "?";
}

export function UserMenu() {
  const session = useSession();
  const router = useRouter();

  if (!session) return null;
  const label = session.user.name ?? session.user.email;

  async function handleLogout() {
    try {
      await logout();
    } catch {
      // Even if the backend call fails, clear the local session mirror and
      // send the user back to login — never strand them on an authenticated
      // screen with a dead session.
    } finally {
      await fetch("/api/session", { method: "DELETE" });
      toast.success("Logged out");
      router.push("/login");
      router.refresh();
    }
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="flex items-center gap-2 rounded-md p-1.5 text-sidebar-foreground outline-none hover:bg-sidebar-accent/10">
          <Avatar className="h-7 w-7">
            <AvatarFallback className="bg-sidebar-accent text-xs text-sidebar-accent-foreground">
              {initials(label)}
            </AvatarFallback>
          </Avatar>
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel className="flex flex-col">
          <span className="flex items-center gap-1 font-medium">
            <UserIcon className="h-3.5 w-3.5" /> {label}
          </span>
          <span className="text-xs font-normal text-muted-foreground">{session.user.account_type}</span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={handleLogout} className="text-destructive focus:text-destructive">
          <LogOut className="mr-2 h-4 w-4" />
          Log out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
