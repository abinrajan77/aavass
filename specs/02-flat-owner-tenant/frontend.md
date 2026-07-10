# Module 2 — Flat, Owner & Tenant Management: Frontend Plan

> Companion files: [`overview.md`](./overview.md) · [`backend.md`](./backend.md) · [`cloud.md`](./cloud.md)
> Read `../00-architecture-and-standards.md` §3 (design system) first — occupancy badges below extend that
> section's status-color rule without overloading it.

## Routes

| Route | Audience | Purpose |
|---|---|---|
| `/towers/[towerId]/flats` | Admin (`MANAGE_RESIDENTS` or `VIEW_TOWER_DATA`) | Flat list/DataTable for the tower |
| `/towers/[towerId]/flats/[flatId]` | Admin | Flat detail page — `Tabs`: **Details**, **Owners**, **Tenants** |
| `/my-flats/[flatId]` | Flat Owner (`MANAGE_OWN_FLAT`) | Owner self-service equivalent of the detail page, permission-gated per field (see below) |

## `/towers/[towerId]/flats` (admin list)

- `DataTable` (TanStack + shadcn `Table`) — columns: Flat No., Floor, Type, Carpet Area, Occupancy `Badge`,
  Primary Owner (name, linked), Active Tenant (name or "—"), row `DropdownMenu` (View, Edit, Deactivate/Reactivate).
- Toolbar: text search (flat number), `Select` filters for Type and Occupancy Status, "Add Flat" button opening a
  `Dialog` + `Form` (react-hook-form + zod).
- Row click opens a `Sheet` (side panel) with a compact summary (flat fields, current primary owner, current
  tenant if any) and a "View full profile" link to `/towers/[towerId]/flats/[flatId]`. The Sheet is for a fast
  glance from the list; the dedicated page is for actually managing owners/tenants/history.
- Occupancy `Badge` mapping — reuses `../00-architecture-and-standards.md` §3.1 where it applies and extends it
  consistently for the two statuses that table doesn't cover (that table is payment-status-first):
  - `Vacant` → `muted` / outline gray badge (this one is literally in the shared table — reuse as-is).
  - `Tenant-occupied` → `accent` (gold) solid badge — visually flags "billing due currently routes to a tenant,"
    a fact billing-relevant to admins.
  - `Owner-occupied` → `secondary` (navy-tinted) outline badge — the default/neutral state.
  - Do **not** reuse `success`/`warning`/`destructive` for occupancy — those are reserved for payment status
    elsewhere in the app and must not be overloaded with a second meaning.
- `Skeleton` rows while loading; `Sonner` toasts on create/edit/deactivate success or error.

## `/towers/[towerId]/flats/[flatId]` (admin detail)

- Page header: flat number/floor/type, occupancy `Badge`, "Edit" and "Deactivate" actions (`MANAGE_RESIDENTS`
  required; `Deactivate` disabled with a tooltip if the flat has open dues — see `overview.md` Edge cases).
- `Tabs`:
  - **Details** — `Form` for flat_number, floor, type (`Select`), carpet_area_sqft. Admin-only fields.
  - **Owners** — list of active co-owners (name, phone, email, `Badge` "Primary" on the primary contact),
    "Add Co-owner" `Dialog` (search existing global Owner by phone/email or create new), row actions:
    "Make Primary Contact", "Remove" (ends the ownership period — see `backend.md`). Below the active list, a
    collapsed "Ownership History" table (past owners, date_from/date_to) — read-only, never editable.
  - **Tenants** — current active tenant card (name, phone, email, lease dates, "Vacate" button) if one exists,
    else an "Add Tenant" `Dialog` + `Form` with `Calendar`+`Popover` date pickers for lease_start/lease_end. Below:
    a "Tenant History" `DataTable` of past tenants (read-only), sorted by lease_start descending.
  - "Vacate" opens a `Dialog` asking for `vacated_date` (`Calendar`) and a required `Select` for the resulting
    `occupancy_status` (`Owner-occupied` / `Vacant`) — the form cannot submit without this selection (PRD §6.2.3:
    admin specifies the reverted status).

## `/my-flats/[flatId]` (owner self-service)

Same three-`Tabs` layout, permission-scoped:

- **Details** tab: flat fields are **read-only** (no edit form controls rendered) for the owner — `carpet_area`,
  `floor`, `type`, `flat_number` are admin-only per PRD §6.2.1 ("Tower admin can view and edit all flat records").
  Instead this tab shows the owner's own contact fields (phone, email) in an editable `Form` — `MANAGE_OWN_FLAT`
  permits **contact fields only**, not `full_name` or `id_number` (identity fields stay admin-only to prevent an
  owner silently changing who they legally are on record).
- **Owners** tab: read-only list of co-owners on the flat (no add/remove/primary-contact controls) — co-ownership
  changes are legally sensitive and remain `MANAGE_RESIDENTS`-only (admin).
- **Tenants** tab: full parity with the admin view — owners can Add Tenant and Vacate Tenant (PRD §6.2.3: "Tower
  admin and the flat owner can add/edit tenant details for a flat"; §6.6: owner can update tenant info and the
  resulting occupancy status). Tenant history is visible identically to the admin view (PRD §6.2.3: "visible to
  both the flat owner ... and the tower admin").

If the logged-in owner has flats in multiple towers, the tower/flat context switcher itself is a Module 5 concern
(owner dashboard) — this module only guarantees `GET /api/v1/me/flats` returns the full cross-tower list it needs
(see `backend.md`).

`<Can permission="MANAGE_OWN_FLAT">` component-level guards hide edit affordances client-side; the backend
dependency (`require_permission`) is the actual boundary per `../00-architecture-and-standards.md` §5.3.

## Data fetching / validation

- TanStack Query for all list/detail reads; mutations via typed fetch client + `useMutation`, invalidating the
  relevant flat/owner/tenant query keys on success (e.g. adding a tenant invalidates both the tenant list and the
  flat detail query, since `occupancy_status` changes as a side effect).
- zod schemas mirror the backend Pydantic models 1:1 (`TenantCreate`, `TenantVacate`, `OwnerContactUpdate`, etc.)
  so client-side validation errors match server-side ones (e.g. `lease_end >= lease_start`).
- magicui: none used in this module — it is pure data-density CRUD (tables/forms), not a dashboard surface; per
  `../00-architecture-and-standards.md` §3.2 rule of thumb, magicui accents are reserved for dashboard/landing
  surfaces (Module 5), not here.

## Frontend test plan

**Component**
- Occupancy `Badge` renders the correct variant/token for each of the three statuses and never reuses
  `success`/`warning`/`destructive`.
- The vacate `Dialog`'s submit button stays disabled until `occupancy_status` is selected.
- `/my-flats/[flatId]` Details tab renders `carpet_area`/`floor`/`type`/`flat_number` as plain text (no `<input>`
  present in the DOM) for a session with only `MANAGE_OWN_FLAT`.

**E2E** (Playwright against a seeded staging-like environment)
- Admin logs in → navigates to `/towers/[towerId]/flats` → adds a new flat → flat appears in the DataTable with a
  `Vacant` badge.
- Admin opens the flat → Owners tab → adds an owner as primary contact → Owners tab shows the owner with a
  "Primary" badge.
- Admin adds a tenant on the Tenants tab → flat detail badge updates to `Tenant-occupied` without a page reload
  (optimistic update / refetch) → admin marks the tenant vacated, selecting `Owner-occupied` in the dialog → badge
  reverts to `Owner-occupied` and the tenant now appears under Tenant History.
- Flat owner logs in → `/my-flats/[flatId]` → Details tab shows flat fields as read-only text (no editable
  inputs rendered) → owner edits their phone number and saves → change persists and is reflected on the admin's
  view of the same owner.
- Flat owner adds a tenant for their own flat from `/my-flats/[flatId]` → tenant appears immediately in the
  admin's `/towers/[towerId]/flats/[flatId]` Tenants tab (same underlying data, both surfaces read the same API).

**What must NOT break (frontend-relevant regressions)**
- The occupancy badge color mapping must never collide with the payment-status color mapping used elsewhere in
  the app (Modules 3/4) — a shared `<StatusBadge>` component should take an explicit `kind: "occupancy" | "payment"`
  prop rather than inferring color from the string value, to make this collision structurally impossible.
- Identity fields (`full_name`, `id_number`) must never render as editable inputs in the owner self-service view,
  even if a future refactor changes the tab layout.
