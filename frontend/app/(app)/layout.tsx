import { redirect } from "next/navigation";
import { getSession } from "@/lib/session";
import { SessionProvider } from "@/components/providers/session-provider";

/**
 * Wraps every authenticated route group with the session context (see
 * lib/session.ts and components/providers/session-provider.tsx). Purely a
 * server->client data bridge — the visual shell (Sidebar/Breadcrumb/etc.) is
 * rendered per-section (see app/(app)/admin/layout.tsx and
 * app/(app)/towers/[towerId]/layout.tsx) since the nav content differs
 * between the superuser admin area and a tower's own shell.
 *
 * middleware.ts already redirects unauthenticated requests before this
 * renders; this redirect is defense-in-depth for direct server rendering.
 */
export default async function AuthenticatedLayout({ children }: { children: React.ReactNode }) {
  const session = await getSession();
  if (!session) {
    redirect("/login");
  }

  return <SessionProvider session={session}>{children}</SessionProvider>;
}
