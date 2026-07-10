# Spec: Module 2 — Flat, Owner & Tenant Management (Overview)

> Read `../00-architecture-and-standards.md` first — this spec follows its conventions (design system, latency
> table, RBAC catalog, API conventions) verbatim and does not redefine them.
> Companion files: [`frontend.md`](./frontend.md) · [`backend.md`](./backend.md) · [`cloud.md`](./cloud.md)
> Maps to PRD §6.2, §9 (resident-registry user stories), §10 (assumptions), §13 (glossary).
> PRD milestone: M1 (part) — this module must land before Modules 3, 4, 5 start (they read its data as source of truth).

## Problem

Tower admins currently have no structured record of which flats exist, who legally owns each one, and who is
currently living there. Co-ownership, ownership transfers, and tenant turnover are common and today produce no
audit trail — so when a billing due needs to be assigned to "the current resident," nobody can say authoritatively
who that is. Flat owners also have no self-service way to keep their own contact and tenant details current. This
module is the single source of truth for Flat / Owner / Tenant data that Modules 3 (billing), 4 (special
collections/expenditure), and 5 (reporting/owner portal) all read from.

## Non-goals

- No billing, dues, receipts, or payment logic — Module 3/4 own dues; this module only exposes the data
  (`occupancy_status`, active tenant, primary owner) they need to compute "current resident."
- No parking slot or amenity tracking (PRD §3.2 non-goal).
- No per-flat maintenance formula (Module 3 concern).
- No SMS/WhatsApp notification dispatch (Module 5 / v1.1).
- No complex-level cross-tower reconciliation — an Owner entity can span towers, but each Flat/Tower remains
  isolated per PRD §7 multi-tenancy.
- No association-member/role management (Module 1) — this module only *consumes* `require_permission()` and the
  authenticated user/tower context Module 1 provides.
- No new file upload flows — no attachments belong to Flat/Owner/Tenant records in v1.0.

## Data model contract for downstream modules (read this first)

Modules 3/4/5 must never re-derive resident/ownership logic — they read these two guarantees this module enforces
at the DB level:

1. **At most one active tenant per flat** — enforced by a partial unique index on `tenants(flat_id) WHERE is_active`.
2. **Exactly one primary owner per flat at any time** (while the flat has any owner) — enforced by a partial unique
   index on `flat_ownerships(flat_id) WHERE date_to IS NULL AND is_primary_contact`.

Given those two invariants, "current resident" for a flat is always computable as: the active tenant if
`flats.occupancy_status = 'tenant_occupied'`, else the primary owner. Module 3's billing-cycle generator and
Module 5's notification-recipient logic both rely on this being true at all times — any schema change to these
tables must preserve both constraints. Full table definitions live in [`backend.md`](./backend.md).

## Edge cases

- **Adding a second active tenant to a flat that already has one** → reject with `409 ONE_ACTIVE_TENANT` before
  any write; the existing active tenant must be vacated first. Covered by both an app-level pre-check (row-locked)
  and the `tenants` partial unique index as a backstop.
- **Owner linked to flats across multiple towers** → `Owner` and `FlatOwnership` are not tower-scoped tables;
  `GET /api/v1/me/flats` returns all currently-owned flats regardless of tower. `require_permission` still
  isolates every tower-scoped read/write (an owner can't see flat *details* of a tower they don't have a
  `FlatOwnership` row in — only their own flats, never the whole tower roster).
- **Deactivating a flat that has open dues** → `POST .../deactivate` checks for any `maintenance_dues` or
  `special_collection_dues` row for that flat with status in `pending`/`overdue` (Modules 3/4 tables, read-only
  cross-module query against the shared DB) and returns `409 OPEN_DUES_EXIST` with the count of open dues in the
  error payload if any are found. Admin must resolve/waive dues (a Module 3/4 concern) before a flat can be
  deactivated.
- **Marking a tenant vacated without specifying the new occupancy status** → `TenantVacate.occupancy_status` has
  no default and is a required enum restricted to `owner_occupied`/`vacant` (never `tenant_occupied`, which would
  be nonsensical immediately after vacating); omitting it or sending an invalid value returns `422` with a
  `field_errors` entry naming the field.
- **Owner updating their own contact details vs. admin doing it** → `PATCH /api/v1/owners/{owner_id}` accepts a
  wider payload for `MANAGE_RESIDENTS` callers (can also change `full_name`, `id_number`) but the schema for a
  `MANAGE_OWN_FLAT` caller only accepts `phone`/`email` in the first place, so an owner cannot smuggle other
  fields through even via a raw API call.
- **Co-owner removal when they are the primary contact** → `POST .../owners/{ownership_id}/remove`:
  - If the flat has other active co-owners and no `new_primary_owner_id` is supplied in the request →
    `409 PRIMARY_CONTACT_REQUIRED` (admin must nominate the new primary contact atomically with the removal).
  - If the co-owner being removed is the *only* active owner on the flat → `409 LAST_OWNER_ON_FLAT` (a flat must
    always retain at least one active owner; the admin must add a replacement owner before removing the last one).
- **Ownership/tenant history must reflect reality even across corrections** — a `FlatOwnership`/`Tenant` row
  created in error is corrected via `deactivated_at` (soft delete) rather than mutating `date_to`/`is_active` in a
  way that would look like a real historical transition; this keeps "removed" (data-entry mistake) distinguishable
  from "ended" (real-world ownership/tenancy change) in the audit trail.
- **Mid-cycle tenant change does not retroactively alter an already-generated due** — this module only flips
  `occupancy_status`/active tenant; it never reaches into Module 3's `maintenance_dues` to reassign an
  already-generated due (PRD §6.2.3 note) — that immutability is Module 3's responsibility, not this module's, but
  the transition logic here must not attempt it.

## Acceptance criteria

1. GIVEN a tower admin with `MANAGE_RESIDENTS`, WHEN they `POST /api/v1/towers/{tower_id}/flats` with valid
   `flat_number`, `floor`, `type`, `carpet_area_sqft`, THEN a `Flat` row is created with `occupancy_status=vacant`
   and appears in `GET /api/v1/towers/{tower_id}/flats`.
2. GIVEN an existing flat with no owners, WHEN the admin `POST`s a `FlatOwnershipCreate` for a new owner with
   `is_primary_contact=true`, THEN exactly one `flat_ownerships` row exists with `date_to IS NULL` and
   `is_primary_contact=true` for that flat, and `GET .../flats/{flat_id}` returns that owner as `primary_owner`.
3. GIVEN a flat already has one active owner marked primary, WHEN the admin adds a second co-owner also with
   `is_primary_contact=true` in the same request, THEN the system rejects with `409` (or atomically demotes the
   first, per the chosen `PATCH` semantics) — never leaving two active rows with `is_primary_contact=true`.
4. GIVEN a flat with `occupancy_status=vacant` and no active tenant, WHEN a tenant is added via
   `POST .../tenants`, THEN the response tenant has `is_active=true`, and a subsequent
   `GET .../flats/{flat_id}` shows `occupancy_status=tenant_occupied`.
5. GIVEN a flat with an active tenant, WHEN a second `POST .../tenants` is attempted for the same flat, THEN the
   response is `409` with `error_code=ONE_ACTIVE_TENANT` and no new row is created.
6. GIVEN a flat with an active tenant, WHEN the admin calls `POST .../tenants/{tenant_id}/vacate` with
   `occupancy_status=vacant`, THEN the tenant's `is_active` becomes `false`, `vacated_at` is set, and
   `flats.occupancy_status` becomes exactly `vacant` (not defaulted to `owner_occupied`).
7. GIVEN the same flat as above, WHEN `GET .../tenants` is called by the flat's owner via `/my-flats/{flatId}`,
   THEN the response includes the vacated tenant in the history list with correct `lease_start`/`lease_end`, and
   the same history is visible to the tower admin via the admin route.
8. GIVEN a flat owner authenticated with only `MANAGE_OWN_FLAT` for their own flat, WHEN they attempt
   `PUT /api/v1/towers/{tower_id}/flats/{flat_id}` with a changed `carpet_area_sqft`, THEN the request is rejected
   (403, or the field is not present in the schema accepted for that permission tier) and the stored value is
   unchanged.
9. GIVEN the same flat owner, WHEN they `POST .../tenants` for their own flat, THEN the request succeeds (owners
   are permitted to add/vacate tenants for their own flat per PRD §6.2.3/§6.6).
10. GIVEN a co-owner who is the current primary contact and other co-owners exist, WHEN the admin calls
    `.../owners/{ownership_id}/remove` without `new_primary_owner_id`, THEN the response is `409` with
    `error_code=PRIMARY_CONTACT_REQUIRED` and the ownership row is untouched.
11. GIVEN a flat with an unpaid/overdue due recorded in Module 3's tables, WHEN the admin calls
    `.../deactivate`, THEN the response is `409` with `error_code=OPEN_DUES_EXIST` and `flats.deactivated_at`
    remains `NULL`.

## Open questions / inconsistencies to flag (not blocking, but worth a quick confirmation before/while building)

- `../00-architecture-and-standards.md` §2 lists `TenantHistory` as a distinct owned entity for this module; this
  spec implements tenant history as non-active rows of a single `tenants` table rather than a separate table.
  Recommend confirming this with whoever wrote the 00 doc so Module 5's Tenant Register report query targets the
  right table/shape.
- PRD §6.6 says a flat owner "can update ... occupancy status" as if it were a freestanding field, while §6.2.3
  only allows occupancy status to change via tenant add/vacate. This spec resolves the tension by only letting
  owners set `occupancy_status` as part of the required vacate payload (never as a direct standalone edit) — flag
  to product if a direct standalone toggle was actually intended.
- The "open dues" check on flat deactivation requires this module to read Module 3/4's `maintenance_dues` /
  `special_collection_dues` tables directly (same Postgres instance). This is called out here as a cross-module
  coupling point; Module 3/4's owner should confirm the exact table/column names once their spec/migrations land
  so this check doesn't silently no-op against a renamed table.
