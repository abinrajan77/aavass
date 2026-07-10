# Module 1 — Auth, RBAC & Tower/Complex Setup: Frontend Plan

> Companion files: [`overview.md`](./overview.md) · [`backend.md`](./backend.md) · [`cloud.md`](./cloud.md)
> Read `../00-architecture-and-standards.md` §3 (design system) first.

## Routes (Next.js App Router)

| Route | Access | Purpose |
|---|---|---|
| `/login` | public | Email/password login |
| `/forgot-password` | public | Request password reset |
| `/reset-password/[token]` | public | Set new password from emailed/relayed link |
| `/` | authenticated | Redirects based on account type: superuser → `/admin/complexes`, tower admin → `/towers/[towerId]` (their tower, or a tower-picker if they belong to >1), flat owner → Module 5's owner dashboard |
| `/admin/complexes` | superuser only | List/create/edit `ApartmentComplex` records |
| `/admin/complexes/[complexId]/towers` | superuser only | List/create towers within a complex; bootstrap the first `Admin` association member for a new tower |
| `/towers/[towerId]` | tower admin (any permission) or flat owner (`VIEW_TOWER_DATA`) | App shell entry point; renders the module-5-owned dashboard inside this module's shell |
| `/towers/[towerId]/settings/tower-profile` | `MANAGE_COMPLEX` | Edit tower name, floors, flat count, association name; deactivate/reactivate tower |
| `/towers/[towerId]/settings/association-members` | `MANAGE_ASSOCIATION_MEMBERS` | List/add/edit/deactivate association members, assign role |
| `/towers/[towerId]/settings/roles` | `MANAGE_ASSOCIATION_MEMBERS` | List roles; create/edit custom role + permission checkbox matrix |

## Shared app shell (built here, used by every module)

A `Sidebar` (shadcn) with nav items filtered by `session.permissions`, a `Breadcrumb` for the current
tower/settings path, and a `Command` palette bound to `⌘K`/`Ctrl+K` used as the
**tower switcher** for any user (flat owner or association member) who belongs to more
than one tower — it lists towers the user can access and navigates to
`/towers/[towerId]`. `middleware.ts` reads the session cookie, redirects unauthenticated
requests to `/login`, and does a coarse route-level check (`/admin/*` requires
`is_superuser`; `/towers/[towerId]/*` requires the user have *some* access to that
tower — the fine-grained permission check still happens server-side via
`require_permission()`, per `../00-architecture-and-standards.md`'s "frontend check is UX only" rule).

## Components used, per screen

| Screen | Components |
|---|---|
| `/login` | `Form` (react-hook-form + zod), `Card`, `Input`, `Button`, `Alert` for error state |
| `/forgot-password`, `/reset-password/[token]` | `Form`, `Card`, `Input`, `Button` |
| `/admin/complexes` | `DataTable` (TanStack), `Dialog` + `Form` for create/edit, `Sonner` toasts |
| `/admin/complexes/[complexId]/towers` | `DataTable`, `Dialog` + `Form`, `Badge` (active/inactive) |
| `/towers/[towerId]/settings/tower-profile` | `Form` in a `Card` (single-entity detail, not a table), `AlertDialog`-style confirm inside a `Dialog` for deactivate |
| `/towers/[towerId]/settings/association-members` | `DataTable`, `Dialog` + `Form`, `Select` (role dropdown), `Badge` (active/inactive), `Sheet` for a member's detail/audit history |
| `/towers/[towerId]/settings/roles` | `DataTable` (roles list), `Dialog` with a `Checkbox` grid (permission matrix) + `Form`, `Badge` ("System default" on the seeded Admin role) |
| Global shell | `Sidebar`, `Breadcrumb`, `Command` (tower switcher), `Avatar` + `DropdownMenu` (user menu/logout), `Sonner` |

## magicui

**None in this module.** Module 1 is forms, tables, and settings screens —
exactly the "data-density" surfaces `../00-architecture-and-standards.md` §3.2 says magicui
should *not* touch. The one magicui component in the catalog that touches this module's
data — `AnimatedList` for an audit-log activity feed — is a **dashboard** surface owned by
Module 5; Module 1 only needs to expose the data (`GET /audit-log` — see `backend.md`) for
Module 5 to consume. Do not add magicui here.

## Client-side validation (zod, mirroring backend Pydantic)

```ts
const loginSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1, "Password is required"),
});

const createComplexSchema = z.object({
  name: z.string().min(2).max(200),
  address: z.string().min(5).max(500),
});

const createTowerSchema = z.object({
  name: z.string().min(1).max(100),
  code: z.string().regex(/^[A-Z0-9]{2,10}$/, "2-10 uppercase letters/digits"), // used in receipt numbering by Module 3
  totalFloors: z.number().int().positive(),
  totalFlats: z.number().int().positive(),
  associationName: z.string().min(1).max(200),
});

const createAssociationMemberSchema = z.object({
  name: z.string().min(2).max(150),
  email: z.string().email(),
  phone: z.string().regex(/^[6-9]\d{9}$/, "Enter a valid 10-digit Indian mobile number"),
  roleId: z.string().uuid(),
});

const createRoleSchema = z.object({
  name: z.string().min(2).max(80),
  permissionCodes: z.array(z.string()).min(1, "Select at least one permission"),
});
```

## Theme application

- **Login screen**: full-bleed `bg-primary` (deep navy) background, a centered `Card`
  (`bg-card`) with the Aavaas wordmark, form fields using default `--input`/`--border`
  tokens, and the submit `Button` using `bg-accent text-accent-foreground` (warm gold) as
  the one high-emphasis element on an otherwise quiet screen — this is intentional: a
  financial ops tool's login should feel calm and trustworthy, not flashy. Error states use
  `Alert` with `--destructive`.
- **Admin shell**: `Sidebar` uses `bg-primary`/`text-primary-foreground` with the active nav
  item indicated by a `border-l-2 border-accent` (gold) accent bar — the only place gold
  appears outside of status badges and primary CTAs, per the `00` doc's "Navy = structure, Gold =
  emphasis" rule. Content area uses default `bg-background`. `success`/`warning`/`destructive`
  are reserved exclusively for payment status (Paid/Pending/Overdue) per
  `../00-architecture-and-standards.md` §3.1 — association members and roles are not a payment
  concept, so their active/deactivated badges use **no badge** (plain text) for active and a
  `muted` outline badge for deactivated, consistent with how Module 2's occupancy badges avoid
  reusing the payment-status tokens for a second meaning (see
  `../02-flat-owner-tenant/frontend.md`).

## Frontend test plan

**E2E (Playwright or equivalent, against a seeded test tower):**

- Login → dashboard renders only nav items in the `Sidebar` corresponding to the logged-in
  user's granted permissions (e.g., a member without `MANAGE_EXPENDITURE` never sees an
  "Expenditures" nav link, even though the route exists).
- A tower admin with two tower memberships uses the `Command` tower-switcher to move from
  Tower A's shell to Tower B's shell, and the URL/breadcrumb/nav all update to Tower B's
  context with no stale Tower-A data flashing.
- Attempting to navigate directly (via URL) to a `/towers/{otherTowerId}/settings/roles` the
  user isn't a member of redirects to a "not authorized" state rather than rendering a blank
  or partially-loaded page.
- Creating a custom role via the permission checkbox matrix, then inviting a new
  association member with that role, then logging in as that member shows exactly the
  granted permissions' worth of UI — nothing more.

**What must NOT break (frontend-relevant regressions):**

- Nav items must derive from `session.permissions`, never from a hardcoded role-name check
  (e.g. `role === "Admin"`) — a future custom role with a subset of Admin's permissions must
  still see the correct partial nav.
- The tower-switcher must never leave stale data from the previous tower visible during the
  transition (loading state or full unmount/remount of tower-scoped data on switch).
