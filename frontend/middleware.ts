import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { SESSION_COOKIE_NAME, type Session } from "@/lib/session";
import { PERMISSIONS } from "@/lib/permissions";

/**
 * Route-level auth/RBAC gating — per specs/00-architecture-and-standards.md §5.3
 * and specs/01-auth-rbac-tower-setup/frontend.md "Shared app shell".
 *
 * THIS IS UX ONLY. It reads a client-mirrored session cookie (see
 * `lib/session.ts`) to avoid flashing unauthorized screens / doing obviously
 * pointless navigations. The actual security boundary is the FastAPI
 * `require_permission()` / `require_superuser()` dependencies on the backend,
 * which re-validate the httpOnly access token and tower access on every
 * request (specs/00-architecture-and-standards.md §5.3, §6
 * "Multi-tenancy isolation"). A forged or stale cookie here can, at worst,
 * cause a wrong redirect — never unauthorized data access.
 */

const PUBLIC_ROUTES = ["/login", "/forgot-password", "/reset-password"];

function isPublicRoute(pathname: string): boolean {
  return PUBLIC_ROUTES.some((route) => pathname === route || pathname.startsWith(`${route}/`));
}

function readSession(request: NextRequest): Session | null {
  const raw = request.cookies.get(SESSION_COOKIE_NAME)?.value;
  if (!raw) return null;
  try {
    return JSON.parse(raw) as Session;
  } catch {
    return null;
  }
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Never gate framework/static/api-internal paths.
  if (
    pathname.startsWith("/_next") ||
    pathname.startsWith("/api/") ||
    pathname === "/favicon.ico"
  ) {
    return NextResponse.next();
  }

  const session = readSession(request);

  if (isPublicRoute(pathname)) {
    return NextResponse.next();
  }

  if (!session) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  // Coarse gate: /admin/* is superuser-only.
  if (pathname.startsWith("/admin")) {
    if (!session.user.is_superuser) {
      return NextResponse.redirect(new URL("/not-authorized", request.url));
    }
    return NextResponse.next();
  }

  // Coarse gate: /towers/[towerId]/* requires *some* access to that tower.
  // Fine-grained permission checks (e.g. MANAGE_ASSOCIATION_MEMBERS for the
  // roles screen) happen in the page/component via <Can> and, authoritatively,
  // on the backend.
  const towerMatch = pathname.match(/^\/towers\/([^/]+)/);
  if (towerMatch) {
    const towerId = towerMatch[1];
    const hasAccess = session.user.is_superuser || session.towers.some((t) => t.tower_id === towerId);
    if (!hasAccess) {
      return NextResponse.redirect(new URL("/not-authorized", request.url));
    }

    // Module 4 (specs/04-special-collections-expenditure/frontend.md route
    // guard note): "/expenditures/new redirects flat owners away (no
    // MANAGE_EXPENDITURE)". This is UX only, same caveat as the rest of this
    // file — the backend's require_permission("MANAGE_EXPENDITURE") is the
    // real boundary.
    if (
      pathname === `/towers/${towerId}/expenditures/new` &&
      !session.user.is_superuser &&
      !session.permissions.includes(PERMISSIONS.MANAGE_EXPENDITURE)
    ) {
      return NextResponse.redirect(new URL("/not-authorized", request.url));
    }

    return NextResponse.next();
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image).*)"],
};
