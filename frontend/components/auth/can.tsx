"use client";

import { useSession } from "@/components/providers/session-provider";
import { hasPermission, type Permission } from "@/lib/permissions";

/**
 * Component-level permission gate — specs/00-architecture-and-standards.md §5.3:
 * "<Can permission="RECORD_PAYMENT"> hide/disable actions. The frontend check
 * is UX only — the backend dependency is the actual security boundary."
 *
 * Never gate on a role name here — always a permission code, so a future
 * custom role with a subset of another role's permissions renders correctly.
 * `hasPermission()` bypasses this for a superuser, mirroring the backend's
 * `require_permission()` bypass (see that helper's docstring).
 */
export function Can({
  permission,
  fallback = null,
  children,
}: {
  permission: Permission | string;
  fallback?: React.ReactNode;
  children: React.ReactNode;
}) {
  const session = useSession();
  const allowed = hasPermission(session, permission);
  return <>{allowed ? children : fallback}</>;
}
