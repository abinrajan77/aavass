import "server-only";
import { cookies } from "next/headers";
import type { LoginResponse } from "./api/types";

/**
 * Session cookie design note (frontend-only decision, no `/auth/me` endpoint
 * is defined in specs/01-auth-rbac-tower-setup/backend.md):
 *
 * `POST /api/v1/auth/login` sets the real `access_token`/`refresh_token`
 * httpOnly cookies (owned by the backend) AND returns
 * `{ user, permissions, towers }` in its response body. Since middleware and
 * server components need fast, synchronous access to `permissions`/`towers`
 * on every request (per specs/00-architecture-and-standards.md §5.3's
 * `session.permissions` contract) without an extra network round-trip per
 * navigation, the frontend mirrors that response body into its own
 * lightweight, non-httpOnly `aavaas_session` cookie via
 * `app/api/session/route.ts`, immediately after login/refresh succeed.
 *
 * This cookie is NOT a security boundary — it is UX plumbing only. The real
 * boundary is the backend's `require_permission()` dependency validating the
 * httpOnly access token on every API call. If this cookie is stale, missing,
 * or forged, the worst outcome is a wrong nav-item render or a redirect,
 * never data access — the backend re-checks everything.
 */
export const SESSION_COOKIE_NAME = "aavaas_session";

export type Session = LoginResponse;

export async function getSession(): Promise<Session | null> {
  const raw = cookies().get(SESSION_COOKIE_NAME)?.value;
  if (!raw) return null;
  try {
    return JSON.parse(raw) as Session;
  } catch {
    return null;
  }
}

export function hasPermission(session: Session | null, permission: string): boolean {
  if (!session) return false;
  return session.user.is_superuser || session.permissions.includes(permission);
}

export function hasTowerAccess(session: Session | null, towerId: string): boolean {
  if (!session) return false;
  return session.user.is_superuser || session.towers.some((t) => t.tower_id === towerId);
}
