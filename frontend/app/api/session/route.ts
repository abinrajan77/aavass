import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { SESSION_COOKIE_NAME } from "@/lib/session";
import type { LoginResponse } from "@/lib/api/types";

/**
 * Thin same-origin route handler that mirrors the body of a successful
 * `POST /api/v1/auth/login` (or `/auth/refresh`) response into a readable
 * `aavaas_session` cookie so `middleware.ts` and server components can read
 * `session.permissions`/`session.towers` without a network round-trip on
 * every navigation. See `lib/session.ts` for the full rationale — this
 * cookie is UX plumbing only, never a security boundary.
 */
export async function POST(request: NextRequest) {
  const body = (await request.json()) as LoginResponse;

  const res = NextResponse.json({ ok: true });
  res.cookies.set(SESSION_COOKIE_NAME, JSON.stringify(body), {
    httpOnly: false,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    // Mirrors typical access-token lifetime; the backend's httpOnly cookies
    // are the actual auth boundary and expire independently.
    maxAge: 60 * 60 * 24,
  });
  return res;
}

export async function DELETE() {
  const res = NextResponse.json({ ok: true });
  res.cookies.delete(SESSION_COOKIE_NAME);
  return res;
}
