# Aavaas — Frontend

Next.js 14 (App Router, TypeScript) frontend for Module 1 — Auth, RBAC &
Tower/Complex Setup. See `../specs/01-auth-rbac-tower-setup/frontend.md` for
the full spec this build follows, and `../specs/00-architecture-and-standards.md`
for the shared design system ("Tower" theme), latency budgets, and RBAC
enforcement pattern.

## Stack

- Next.js 14 (App Router) + TypeScript + Tailwind CSS v3
- shadcn/ui (Radix primitives, `new-york` style) — Table/DataTable
  (TanStack), Dialog, Sheet, Tabs, Form, Badge, Command, Calendar, Popover,
  Select, DropdownMenu, Avatar, Sonner, Skeleton, Sidebar, Breadcrumb, Alert,
  Card, Input, Button, Checkbox
- react-hook-form + zod (`@hookform/resolvers`)
- TanStack Query (React Query) + TanStack Table
- Playwright for E2E tests

No magicui in this module — per spec, Module 1 is forms/tables/settings,
exactly the data-density surface magicui should not touch (that's Module 5's
dashboard).

## Getting started

```bash
npm install
cp .env.example .env.local   # set NEXT_PUBLIC_API_BASE_URL
npm run dev
```

Open http://localhost:3000. You'll land on `/login` (or be redirected there
by `middleware.ts` if you try any other route without a session).

### Required env vars

| Var | Purpose |
|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | Base URL of the FastAPI backend (`specs/01-auth-rbac-tower-setup/backend.md`). Every call in `lib/api/*` goes to `${NEXT_PUBLIC_API_BASE_URL}/api/v1/...` with `credentials: 'include'`. |

## Session/auth design note (read this before wiring up the real backend)

`POST /api/v1/auth/login` sets the real `access_token`/`refresh_token`
httpOnly cookies (owned by the backend) and returns
`{ user, permissions, towers }` in its body. There is no `/auth/me` endpoint
in the backend spec, but `middleware.ts` and server components need fast,
synchronous access to `session.permissions`/`session.towers` on every
navigation (per `00-architecture-and-standards.md` §5.3). To satisfy that
without a network round-trip per page load, the frontend mirrors the login
response into its own **non-httpOnly** `aavaas_session` cookie via
`app/api/session/route.ts`, called right after login/refresh succeeds (see
`lib/session.ts` for the full rationale).

**This cookie is UX plumbing only, never a security boundary.** The actual
boundary is the backend's `require_permission()`/`require_superuser()`
dependencies re-validating the httpOnly access token on every request. If
this mirrored cookie is stale or missing, the worst outcome is a wrong
redirect or nav render — never unauthorized data access. This is called out
again inline in `middleware.ts` and `lib/session.ts`.

If/when a real `/auth/me` (or equivalent) endpoint is added to the backend,
swap `getSession()` in `lib/session.ts` to call it directly instead.

## Routes built

| Route | Access | Notes |
|---|---|---|
| `/login` | public | |
| `/forgot-password` | public | Always shows the generic "check your email" state (no user enumeration) |
| `/reset-password/[token]` | public | |
| `/` | authenticated | Redirect logic by account type (superuser → `/admin/complexes`, tower admin → their tower or a picker, flat owner → `/owner-dashboard` stub) |
| `/admin/complexes` | superuser only | |
| `/admin/complexes/[complexId]/towers` | superuser only | Tower creation seeds the tower's Admin role |
| `/towers` | authenticated, >1 tower | Tower picker |
| `/towers/[towerId]` | tower access required | Shell entry point; dashboard body is a placeholder (see TODOs) |
| `/towers/[towerId]/settings/tower-profile` | `MANAGE_COMPLEX` | |
| `/towers/[towerId]/settings/association-members` | `MANAGE_ASSOCIATION_MEMBERS` | |
| `/towers/[towerId]/settings/roles` | `MANAGE_ASSOCIATION_MEMBERS` | Permission checkbox matrix |
| `/not-authorized` | authenticated | Redirect target for coarse RBAC gate failures |
| `/owner-dashboard` | authenticated, flat owner | Stub — see TODOs |

Shared app shell (`components/shell/*`): `Sidebar` filtered by
`session.permissions` (never a hardcoded role check), `Breadcrumb`, `⌘K`/`Ctrl+K`
`Command` tower-switcher, `Avatar`+`DropdownMenu` user menu with logout.
`middleware.ts` does coarse route gating and is explicitly commented as
UX-only — the backend `require_permission()`/`require_superuser()`
dependencies are the real boundary.

## Testing

```bash
npx playwright install chromium   # first time only
npm run test:e2e
```

**There is no live backend in this repo yet** (built concurrently by another
agent to the same spec) — every E2E test mocks API responses via
Playwright's `page.route()` against a fake `__mock_api__` path prefix (see
`tests/mocks/api.ts` and `playwright.config.ts`'s `webServer.env`). This is
deliberate, not a silent skip: swap the mocks for the real backend base URL
once Module 1's backend is live, and these tests should keep passing
unchanged since they assert on rendered UI, not mock internals.

Covers the full `frontend.md` test plan:
- `tests/e2e/smoke.spec.ts` — login page renders; unauthenticated redirect to `/login`
- `tests/e2e/permission-filtered-nav.spec.ts` — nav items derive from `session.permissions`, not a role name
- `tests/e2e/tower-switcher.spec.ts` — `Ctrl+K` switches Tower A → Tower B with no stale data
- `tests/e2e/unauthorized-tower-redirect.spec.ts` — direct URL to a tower you're not a member of redirects to `/not-authorized`
- `tests/e2e/custom-role-then-login.spec.ts` — creating a custom role via the checkbox matrix, then a session with exactly that role's permissions, renders exactly the correct partial nav

Other checks:

```bash
npm run typecheck
npm run lint
npm run build
```

## TODOs / handoff notes

- **Backend not live**: every `lib/api/*` call is written to the exact
  contract in `specs/01-auth-rbac-tower-setup/backend.md`, but untested
  against a real server. Once the backend is up, smoke-test each mutation
  (login, create complex/tower, create/deactivate association member,
  create/edit/deactivate role) and fix any drift.
- **`/towers/[towerId]` dashboard body is a placeholder.** Module 5 owns the
  real dashboard (stat cards, BentoGrid, activity feed) — replace
  `app/(app)/towers/[towerId]/page.tsx`'s contents, the shell around it
  should not need to change.
- **`/owner-dashboard` is a stub** redirect target for flat-owner accounts —
  Module 5 owns the real owner portal/context-switch experience.
- **No `/auth/me` endpoint** in the backend spec — see the session design
  note above; revisit if that gets added.
- **Password reset email delivery** is out of scope here (manual-notification
  model per PRD §8) — `/reset-password/[token]` assumes the token is relayed
  to the user out-of-band.
