"use client";

import { useSession } from "@/components/providers/session-provider";
import type { Permission } from "@/lib/permissions";

/**
 * Component-level permission gate — specs/00-architecture-and-standards.md §5.3:
 * "<Can permission="RECORD_PAYMENT"> hide/disable actions. The frontend check
 * is UX only — the backend dependency is the actual security boundary."
 *
 * Never gate on a role name here — always a permission code, so a future
 * custom role with a subset of another role's permissions renders correctly.
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
  const allowed = session?.permissions.includes(permission) ?? false;
  return <>{allowed ? children : fallback}</>;
}
