import { redirect } from "next/navigation";
import { getSession, hasTowerAccess } from "@/lib/session";
import { AppShell } from "@/components/shell/app-shell";
import { SidebarNav } from "@/components/shell/sidebar-nav";

/**
 * `/towers/[towerId]/*` — requires *some* access to that tower (coarse gate,
 * mirrored from middleware.ts; the fine-grained per-screen permission check
 * — e.g. MANAGE_ASSOCIATION_MEMBERS for the roles screen — happens via
 * `<Can>` in the page itself and, authoritatively, on the backend).
 */
export default async function TowerLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: { towerId: string };
}) {
  const session = await getSession();
  if (!hasTowerAccess(session, params.towerId)) {
    redirect("/not-authorized");
  }

  return <AppShell nav={<SidebarNav towerId={params.towerId} />}>{children}</AppShell>;
}
