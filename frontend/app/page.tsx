import { redirect } from "next/navigation";
import { getSession } from "@/lib/session";

/**
 * `/` — redirects by account type, per
 * specs/01-auth-rbac-tower-setup/frontend.md routes table:
 *   - superuser        -> /admin/complexes
 *   - tower admin       -> /towers/[towerId] (their tower, or a picker if >1)
 *   - flat owner        -> Module 5's owner dashboard (stub here; that module
 *                          owns the real screen)
 *
 * middleware.ts already redirects unauthenticated requests to /login before
 * this ever renders, but we guard again for direct server-render safety.
 */
export default async function RootPage() {
  const session = await getSession();

  if (!session) {
    redirect("/login");
  }

  if (session.user.is_superuser) {
    redirect("/admin/complexes");
  }

  if (session.user.account_type === "flat_owner") {
    redirect("/owner-dashboard");
  }

  if (session.towers.length === 1) {
    redirect(`/towers/${session.towers[0].tower_id}`);
  }

  if (session.towers.length > 1) {
    redirect("/towers");
  }

  // No tower access at all — shouldn't normally happen for a provisioned
  // association member, but fail safe rather than 500.
  redirect("/not-authorized");
}
