import Link from "next/link";
import { ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";

/**
 * Rendered when middleware.ts (or a layout's defense-in-depth check) blocks
 * a direct-URL navigation to a tower/admin route the session doesn't have
 * access to — per the frontend test plan: "redirects to a 'not authorized'
 * state rather than rendering a blank or partially-loaded page."
 */
export default function NotAuthorizedPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-background px-4 text-center">
      <ShieldAlert className="h-10 w-10 text-muted-foreground" />
      <h1 className="text-xl font-semibold text-foreground">You don&apos;t have access to this page</h1>
      <p className="max-w-sm text-sm text-muted-foreground">
        Your account isn&apos;t a member of this tower, or doesn&apos;t have the permission required to
        view it. If you think this is a mistake, contact your tower admin.
      </p>
      <Button asChild variant="secondary">
        <Link href="/">Back to home</Link>
      </Button>
    </div>
  );
}
