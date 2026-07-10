import { redirect } from "next/navigation";
import { getSession } from "@/lib/session";
import { AppShell } from "@/components/shell/app-shell";
import { AdminSidebarNav } from "@/components/shell/admin-sidebar-nav";

/** `/admin/*` — superuser only (specs/01-auth-rbac-tower-setup/overview.md "Design decision"). */
export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  const session = await getSession();
  if (!session?.user.is_superuser) {
    redirect("/not-authorized");
  }

  return <AppShell nav={<AdminSidebarNav />}>{children}</AppShell>;
}
