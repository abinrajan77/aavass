import { redirect } from "next/navigation";
import { getSession } from "@/lib/session";

/**
 * Placeholder redirect target for flat-owner accounts. The real owner
 * dashboard/context-switch UI is owned by Module 5
 * (specs/05-reporting-owner-portal-notifications) — this route only exists
 * so Module 1's `/` redirect logic (per the routes table) has somewhere
 * concrete to send a flat owner today. Module 5 should replace this file's
 * contents with the real dashboard when it lands.
 */
export default async function OwnerDashboardStubPage() {
  const session = await getSession();
  if (!session) {
    redirect("/login");
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-background px-4 text-center">
      <h1 className="text-xl font-semibold text-foreground">Owner dashboard coming soon</h1>
      <p className="max-w-md text-sm text-muted-foreground">
        This is a placeholder. The flat-owner dashboard and context-switch experience is built by
        Module 5 (Reporting, Owner Portal &amp; Notifications) — see
        specs/05-reporting-owner-portal-notifications/frontend.md.
      </p>
    </div>
  );
}
