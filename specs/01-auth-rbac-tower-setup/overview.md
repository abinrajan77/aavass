# Spec: Module 1 — Auth, RBAC & Tower/Complex Setup (Overview)

> Module 1 of 5. Maps to PRD milestone M1 (part). Owns: `User`, `Permission`, `Role`,
> `RolePermission`, `AssociationMember`, `ApartmentComplex`, `Tower`, `audit_log`.
> Every other module (`02`–`05`) depends on this module's auth guard, `require_permission()`
> dependency, and tower-scoping — land this first.
> Read `../00-architecture-and-standards.md` before this doc; conventions defined there
> (design system, latency budgets, RBAC catalog, API conventions) are not repeated here
> except where this module extends them.
> Companion files: [`frontend.md`](./frontend.md) · [`backend.md`](./backend.md) · [`cloud.md`](./cloud.md)

## Problem

Aavaas has no foundation yet. There is no way for a user to authenticate, no way to know
what a logged-in user is allowed to do, and no representation of the complex → tower
hierarchy that every other entity (flats, billing, expenditures) hangs off of. Without
this module, nothing else can be tower-scoped, permission-checked, or audited. Module 1
builds: login (JWT access/refresh), the RBAC engine (permissions, roles, role-permission
mapping, association members), `ApartmentComplex`/`Tower` CRUD, and the shared
`audit_log` table + write helper that Modules 3 and 4 will call into for financial/config
changes.

## Non-goals

- **No complex-level admin/tenant role.** Per PRD §10, each tower operates independently;
  there is no consolidated cross-tower dashboard or cross-tower reporting persona. (See
  "Design decision" callout below for how `ApartmentComplex`/`Tower` creation is handled
  instead, since *someone* has to create the first tower.)
- **No custom attribute/conditional permission rules.** Roles are a flat set of permission
  codes (checkbox matrix), not a rules engine. This satisfies PRD §4.2's extensibility
  requirement ("future roles ... no code changes required") without over-building.
- **No OAuth/SSO/social login.** Email + password only in v1.0.
- **No self-service signup.** Association members and flat owners are provisioned by an
  existing admin (tower admin invites association members; flat-owner `User` accounts are
  created by Module 2 when an `Owner` record is created) — there is no public
  "create account" page.
- **No MFA.** Out of scope for v1.0; the `users` table leaves room for it later
  (not designed here).
- **No org-wide/global search.** The `Command` component is used only for the tower
  context-switcher, not a general search palette, in this module.
- **No hard deletes anywhere in this module.** Consistent with PRD §7 Data Integrity —
  complexes, towers, roles, and association members are deactivated, never deleted.

### Design decision — who creates the first `ApartmentComplex`/`Tower`?

PRD §10 states there is no complex-level admin role for *tenants*, but PRD §6.1.1 still
requires someone to "create and edit the apartment complex record" and "add/edit/deactivate
towers." The `../00-architecture-and-standards.md` permission catalog even lists
`MANAGE_COMPLEX`, yet its RBAC data model scopes `roles` to a single `tower_id` — there is
no tower yet when a complex is first being set up. This module resolves the gap with a
**platform-admin flag**, not a tenant-facing role:

- `users.is_superuser boolean not null default false` — set only for Aavaas internal
  operations staff (seeded via a one-off script/migration, never exposed as a UI role a
  tenant can grant).
- A `require_superuser()` dependency (separate from `require_permission()`) guards
  `ApartmentComplex` create/edit and `Tower` create + the bootstrapping of a tower's first
  `Admin`-role `AssociationMember`.
- Once a tower exists with its seeded `Admin` role and at least one association member,
  that tower's own admins take over day-to-day tower profile edits (name, floor/flat
  counts, association name) via the ordinary `MANAGE_COMPLEX` permission, tower-scoped —
  they cannot create new towers/complexes or see other towers.

This keeps the PRD's "no complex-level admin *role*" promise (no tenant persona spans
towers) while giving a concrete, buildable answer to "who calls `POST /complexes`."
**Flag for product/architecture sign-off**: confirm this matches intent before Module 1
ships, since it is not explicit in the PRD or the `00` doc.

## Edge cases

- **User has no `AssociationMember` row for the tower they're hitting** (never invited, or
  invited to a different tower) → `require_permission()` returns `403 TOWER_ACCESS_DENIED`,
  treated as zero permissions, not a 500 or a null-pointer.
- **Cross-tower access attempt**: a valid tower-admin token for Tower A calls
  `GET /api/v1/towers/{B}/...` → `403 TOWER_ACCESS_DENIED`, not `404` (don't confirm or
  deny Tower B's existence to a non-member).
- **Deactivating a tower with active flats/dues**: blocked with
  `409 TOWER_HAS_ACTIVE_FINANCIALS` if any `Pending`/`Overdue` maintenance or special-collection
  due exists. Deactivation does **not** cascade to flats/dues even once allowed — financial
  history must remain intact and queryable; only new mutating writes (new billing cycles,
  new members, edits) are blocked via `409 TOWER_INACTIVE`.
- **Deactivating the last `Admin`-role association member of a tower** → blocked,
  `409 LAST_ADMIN` — a tower can never be left with zero members able to manage it.
- **Editing/deactivating the seeded system-default `Admin` role itself** → blocked,
  `409 ROLE_IMMUTABLE`. This is what guarantees `LAST_ADMIN` is enforceable and prevents
  accidental self-lockout at the role-definition level.
- **Editing a custom (non-default) role to remove `MANAGE_ASSOCIATION_MEMBERS`, including by
  a user who currently holds that exact role** → allowed (not blocked), but the UI shows a
  warning ("this may remove your own ability to manage roles"). Not a hard block because the
  immutable `Admin` role is always available as a recovery path for another admin.
- **Association member deactivated while they still own `audit_log` history** → allowed.
  `audit_log.user_id` is never cascade-deleted (no hard deletes exist in this schema at
  all), and `actor_label` preserves a readable snapshot of who performed the action even if
  the `AssociationMember`/`User` record is later deactivated or renamed.
- **Email reused across account types** (e.g., a flat owner's email is also invited as an
  association member — plausible, since an owner can also be the treasurer): the system
  links the existing `User` row rather than erroring on duplicate email; a single `User` can
  simultaneously have `account_type='flat_owner'` history via Module 2's `FlatOwnership` and
  an `AssociationMember` row here. (`users.email` stays globally unique; `account_type`
  reflects how the account was first provisioned but does not block dual context.)
- **JWT expired mid-session** → frontend transparently calls `/auth/refresh`; if the refresh
  token is also expired or revoked, `401` forces a full re-login (no infinite refresh loop).
- **Concurrent sessions across devices**: multiple valid `refresh_tokens` rows per user are
  expected (one per device/browser); logging out on one device revokes only that token
  family, not all of the user's sessions.
- **Superuser creates a tower with `total_floors <= 0` or `total_flats <= 0`** →
  `422` validation error from Pydantic, never reaches the DB.
- **`page_size` beyond the max (100)** → `422` with a `field_errors` entry, per the `00` doc's
  error envelope — never silently clamped, so tests can assert the exact bound.
- **Password reset requested for a non-existent email** → always returns `202`
  regardless (no user-enumeration via response codes/timing).

## Acceptance criteria

1. GIVEN a valid tower-admin user, WHEN they `POST /api/v1/auth/login` with correct
   credentials, THEN the response sets `access_token`/`refresh_token` httpOnly cookies and
   returns their `permissions` array and the list of `towers` they belong to.
2. GIVEN an incorrect password, WHEN `POST /api/v1/auth/login` is called, THEN the response
   is `401` with a generic `INVALID_CREDENTIALS` error (does not reveal whether the email
   exists).
3. GIVEN a tower admin whose role includes `RECORD_PAYMENT`, WHEN they call an endpoint
   guarded by `require_permission("RECORD_PAYMENT")` for their own tower, THEN the request
   proceeds (allow path).
4. GIVEN a tower admin whose role does **not** include `CREATE_BILLING_CYCLE`, WHEN they
   call an endpoint guarded by `require_permission("CREATE_BILLING_CYCLE")`, THEN the
   response is `403 PERMISSION_DENIED` (deny path).
5. GIVEN a tower admin belonging only to Tower A, WHEN they call any
   `/api/v1/towers/{B}/...` endpoint for Tower B, THEN the response is
   `403 TOWER_ACCESS_DENIED` regardless of what permission Tower B's route requires
   (tower isolation).
6. GIVEN a superuser, WHEN they `POST /api/v1/complexes/{id}/towers`, THEN a `Tower` row is
   created **and** a `Role` row with `is_system_default=true, name='Admin'` is seeded with
   every permission in the catalog attached via `role_permissions`.
7. GIVEN any write to `role_permissions`, `Tower`, or `AssociationMember` via this module's
   routers, WHEN the request succeeds, THEN exactly one `audit_log` row is created in the
   same DB transaction with correct `before`/`after` JSON, the acting user's id, and a
   populated `actor_label` — a failed transaction must not leave an orphaned audit row.
8. GIVEN a tower with an `Overdue` maintenance due, WHEN an admin calls
   `POST /api/v1/towers/{tower_id}/deactivate`, THEN the response is
   `409 TOWER_HAS_ACTIVE_FINANCIALS` and the tower remains active.
9. GIVEN a tower with exactly one active `Admin`-role member, WHEN that member is
   deactivated via `POST /.../association-members/{id}/deactivate`, THEN the response is
   `409 LAST_ADMIN` and the member remains active.
10. GIVEN the seeded `Admin` role, WHEN a `PUT` is attempted against
    `/api/v1/towers/{tower_id}/roles/{admin_role_id}`, THEN the response is
    `409 ROLE_IMMUTABLE` and no `role_permissions` rows change.
11. GIVEN a logged-in user, WHEN their access token expires and the frontend calls
    `/api/v1/auth/refresh` with a valid, unexpired, unrevoked refresh token, THEN new
    access/refresh cookies are issued and the old refresh token is invalidated (single-use
    rotation).
12. GIVEN a flat owner (no `AssociationMember` row anywhere), WHEN they call a
    tower-admin-only endpoint like `POST /api/v1/towers/{tower_id}/roles`, THEN the response
    is `403` (either `TOWER_ACCESS_DENIED` or `PERMISSION_DENIED`, never a 500).

## Open questions / inconsistencies to flag

- **Superuser/bootstrap mechanism**: `MANAGE_COMPLEX` is in the `../00-architecture-and-standards.md`
  permission catalog and `roles` are tower-scoped, but nothing in that doc defines how the
  *first* tower in a complex gets created. This spec introduces `users.is_superuser` as a
  platform-admin flag (not a tenant RBAC role) to resolve this — flagged for
  architecture/product sign-off since it's new.
- **`audit_log` schema extension**: this module's `audit_log` table adds `actor_label`
  (name/email snapshot for post-deactivation readability) and makes `tower_id`/`user_id`
  nullable (for complex-level and system-generated entries) beyond the exact column list in
  `../00-architecture-and-standards.md` §6. Recommend folding these into the canonical `00`
  doc so Modules 3/4 build against the same shape.
- **UUID convention**: this module assumes UUID primary keys via `gen_random_uuid()` since
  `00` doesn't specify an ID convention — recommend other module owners follow suit for
  consistency (already reflected in Modules 2–5).
