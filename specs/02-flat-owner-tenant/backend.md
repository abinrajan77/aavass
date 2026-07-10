# Module 2 — Flat, Owner & Tenant Management: Backend Plan

> Companion files: [`overview.md`](./overview.md) · [`frontend.md`](./frontend.md) · [`cloud.md`](./cloud.md)
> Read `../00-architecture-and-standards.md` §5 (RBAC) and §6 (API conventions) first.

## SQLAlchemy tables

```python
class Flat(Base):
    __tablename__ = "flats"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tower_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("towers.id"), nullable=False, index=True)
    flat_number: Mapped[str] = mapped_column(String(20), nullable=False)
    floor: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(Enum("1BHK", "2BHK", "3BHK", "OTHER", name="flat_type"), nullable=False)
    carpet_area_sqft: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    occupancy_status: Mapped[str] = mapped_column(
        Enum("owner_occupied", "tenant_occupied", "vacant", name="occupancy_status"),
        nullable=False, default="vacant",
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
    deactivated_at: Mapped[datetime | None] = mapped_column(nullable=True)

    __table_args__ = (
        # one active flat_number per tower
        Index("uq_flat_tower_number_active", "tower_id", "flat_number",
              unique=True, postgresql_where=text("deactivated_at IS NULL")),
    )


class Owner(Base):
    __tablename__ = "owners"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # nullable: an owner can exist before/without a login account (admin-entered); linked once they register
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), unique=True, nullable=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=True)
    id_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
    deactivated_at: Mapped[datetime | None] = mapped_column(nullable=True)
    # NOTE: Owner is deliberately NOT tower-scoped — PRD §6.2.2 "An owner may be linked to
    # multiple flats across towers." Tower isolation is enforced at the FlatOwnership/Flat level.


class FlatOwnership(Base):
    __tablename__ = "flat_ownerships"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    flat_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("flats.id"), nullable=False, index=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("owners.id"), nullable=False, index=True)
    is_primary_contact: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    date_from: Mapped[date] = mapped_column(Date, nullable=False)
    date_to: Mapped[date | None] = mapped_column(Date, nullable=True)  # NULL = currently active
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

    __table_args__ = (
        # exactly one primary contact among currently-active ownerships, per flat
        Index("uq_flat_primary_contact_active", "flat_id",
              unique=True, postgresql_where=text("date_to IS NULL AND is_primary_contact")),
    )
    # NOTE: rows are never deleted or "soft deleted" — an ownership ends by setting date_to,
    # which IS the audit history (PRD §6.2.2 "System tracks ownership history").


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    flat_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("flats.id"), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=True)
    id_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    lease_start: Mapped[date] = mapped_column(Date, nullable=False)
    lease_end: Mapped[date | None] = mapped_column(Date, nullable=True)  # planned/actual end; nullable while ongoing
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    vacated_at: Mapped[datetime | None] = mapped_column(nullable=True)
    vacated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
    deactivated_at: Mapped[datetime | None] = mapped_column(nullable=True)  # for erroneous-entry correction only

    __table_args__ = (
        Index("uq_tenant_flat_active", "flat_id", unique=True, postgresql_where=text("is_active")),
    )
```

`Tenant` doubles as its own history table (per-row `is_active=false` + `vacated_at` marks a past tenant) — there is
no separate `tenant_history` table; the module-ownership table in `../00-architecture-and-standards.md` §2 lists
`TenantHistory` as a concept, implemented here as the non-active rows of `tenants`, not a distinct table (see
[`overview.md`](./overview.md) "Open questions").

## Pydantic schemas (request/response shape, abbreviated to key fields)

```python
class FlatCreate(BaseModel):
    flat_number: str
    floor: int
    type: Literal["1BHK", "2BHK", "3BHK", "OTHER"]
    carpet_area_sqft: Decimal

class FlatUpdate(BaseModel):
    flat_number: str | None = None
    floor: int | None = None
    type: Literal["1BHK", "2BHK", "3BHK", "OTHER"] | None = None
    carpet_area_sqft: Decimal | None = None
    # occupancy_status is NEVER directly settable via this schema — only via tenant add/vacate transitions

class FlatOut(BaseModel):
    id: UUID
    tower_id: UUID
    flat_number: str
    floor: int
    type: str
    carpet_area_sqft: Decimal
    occupancy_status: Literal["owner_occupied", "tenant_occupied", "vacant"]
    primary_owner: OwnerSummary | None
    active_tenant: TenantSummary | None
    deactivated_at: datetime | None

class OwnerCreate(BaseModel):
    full_name: str
    phone: str
    email: EmailStr | None = None
    id_number: str | None = None
    is_primary_contact: bool = False
    date_from: date

class OwnerContactUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # the ONLY fields MANAGE_OWN_FLAT may write; full_name/id_number require MANAGE_RESIDENTS
    phone: str | None = None
    email: EmailStr | None = None

class FlatOwnershipUpdate(BaseModel):
    is_primary_contact: bool | None = None
    new_primary_owner_id: UUID | None = None  # required when removing the current primary contact (see below)

class TenantCreate(BaseModel):
    full_name: str
    phone: str
    email: EmailStr | None = None
    id_number: str | None = None
    lease_start: date
    lease_end: date | None = None

    @model_validator(mode="after")
    def check_dates(self):
        if self.lease_end and self.lease_end < self.lease_start:
            raise ValueError("lease_end must not be before lease_start")
        return self

class TenantVacate(BaseModel):
    vacated_date: date
    occupancy_status: Literal["owner_occupied", "vacant"]  # required — no default (PRD §6.2.3)
```

## Routes

All under the module's tower-scoped prefix per `../00-architecture-and-standards.md` §6; all responses
use the shared pagination envelope and RFC7807-style error format; all list/mutations pass through
`require_permission(...)`:

| Method | Path | Permission | Notes |
|---|---|---|---|
| `GET` | `/api/v1/towers/{tower_id}/flats` | `VIEW_TOWER_DATA` | paginated, filters: `type`, `occupancy_status`, `q` (flat_number search) |
| `POST` | `/api/v1/towers/{tower_id}/flats` | `MANAGE_RESIDENTS` | body `FlatCreate`; `occupancy_status` defaults `vacant` |
| `GET` | `/api/v1/towers/{tower_id}/flats/{flat_id}` | `VIEW_TOWER_DATA` (admin) or `MANAGE_OWN_FLAT` (owner, own flat only) | returns `FlatOut` |
| `PUT` | `/api/v1/towers/{tower_id}/flats/{flat_id}` | `MANAGE_RESIDENTS` | body `FlatUpdate`; 404 if not found in this tower, 409 `IMMUTABLE_RECORD` if `deactivated_at` set |
| `POST` | `/api/v1/towers/{tower_id}/flats/{flat_id}/deactivate` | `MANAGE_RESIDENTS` | soft-delete; 409 `OPEN_DUES_EXIST` if unpaid dues found (see overview.md Edge cases) |
| `POST` | `/api/v1/towers/{tower_id}/flats/{flat_id}/reactivate` | `MANAGE_RESIDENTS` | clears `deactivated_at` |
| `GET` | `/api/v1/towers/{tower_id}/flats/{flat_id}/owners` | `VIEW_TOWER_DATA` / `MANAGE_OWN_FLAT` (own) | includes `is_active` current + historical rows (history always visible) |
| `POST` | `/api/v1/towers/{tower_id}/flats/{flat_id}/owners` | `MANAGE_RESIDENTS` | body `OwnerCreate` (or `{owner_id, date_from, is_primary_contact}` to link an existing global Owner); creates `FlatOwnership` row |
| `PATCH` | `/api/v1/towers/{tower_id}/flats/{flat_id}/owners/{ownership_id}` | `MANAGE_RESIDENTS` | body `FlatOwnershipUpdate`; flips `is_primary_contact` transactionally (unsets old, sets new) |
| `POST` | `/api/v1/towers/{tower_id}/flats/{flat_id}/owners/{ownership_id}/remove` | `MANAGE_RESIDENTS` | body `{effective_date, new_primary_owner_id?}`; sets `date_to`; never a hard delete |
| `PATCH` | `/api/v1/owners/{owner_id}` | `MANAGE_RESIDENTS` (any field) or `MANAGE_OWN_FLAT` (self, `OwnerContactUpdate` fields only) | global (non-tower-scoped) route since Owner spans towers |
| `GET` | `/api/v1/towers/{tower_id}/flats/{flat_id}/tenants` | `VIEW_TOWER_DATA` / `MANAGE_OWN_FLAT` (own) | full history, active first, then past ordered by `lease_start desc` |
| `POST` | `/api/v1/towers/{tower_id}/flats/{flat_id}/tenants` | `MANAGE_RESIDENTS` or `MANAGE_OWN_FLAT` (own flat) | body `TenantCreate`; 409 `ONE_ACTIVE_TENANT` if an active tenant already exists; on success, sets `flats.occupancy_status = 'tenant_occupied'` in the same DB transaction |
| `PATCH` | `/api/v1/towers/{tower_id}/flats/{flat_id}/tenants/{tenant_id}` | `MANAGE_RESIDENTS` or `MANAGE_OWN_FLAT` (own flat) | corrections to phone/email/lease_end while still active; does not touch `is_active` |
| `POST` | `/api/v1/towers/{tower_id}/flats/{flat_id}/tenants/{tenant_id}/vacate` | `MANAGE_RESIDENTS` or `MANAGE_OWN_FLAT` (own flat) | body `TenantVacate`; sets `is_active=false`, `vacated_at`, `lease_end` (if unset); sets `flats.occupancy_status` to the given value in the same transaction; 422 if `occupancy_status` missing/invalid |
| `GET` | `/api/v1/me/flats` | authenticated Flat Owner | cross-tower list of flats where the caller is a current (`date_to IS NULL`) owner — feeds the owner dashboard/tower-switcher (Module 5 UI, this module's data) |

## Occupancy auto-transition implementation

Implemented at the service layer (not a DB trigger, to keep business logic in one reviewable place and to let it
emit the `audit_log` row in the same unit of work):

- `create_tenant(flat_id, payload)`: opens one DB transaction → `SELECT ... FOR UPDATE` the flat row (prevents a
  race where two concurrent requests both pass the "no active tenant" check) → check no active tenant exists (else
  raise `409 ONE_ACTIVE_TENANT`) → insert `Tenant` row → update `flats.occupancy_status = 'tenant_occupied'` →
  insert `audit_log` (`action="tenant_added"`) → commit. The partial unique index on `tenants` is the second line
  of defense if the row lock is somehow bypassed (e.g. a future direct-SQL migration script).
- `vacate_tenant(tenant_id, payload)`: same transaction pattern → verify the tenant row is currently active (else
  `409 IMMUTABLE_RECORD`/`404`) → set `is_active=false`, `vacated_at=now()`, `lease_end = lease_end or vacated_date`
  → update `flats.occupancy_status = payload.occupancy_status` (admin/owner-specified, PRD §6.2.3) → insert
  `audit_log` (`action="tenant_vacated"`, before/after occupancy_status) → commit.
- Both endpoints re-validate `tower_id` against the caller's accessible towers via `require_permission`, and for
  `MANAGE_OWN_FLAT` callers additionally verify the flat is one they currently own (via `flat_ownerships`) before
  any of the above runs.

## Cross-module read contract

Modules 3/4 read `flats.occupancy_status`, the active `tenants` row, and the primary `flat_ownerships` row directly
(same Postgres instance, read-only queries) to resolve "current resident" — no HTTP call between services for
this. Module 2 does not expose a bespoke "current resident" endpoint in v1.0; if Module 3/4 need one repeatedly,
consider promoting the join to a DB view in a later iteration (not required now).

## Backend test plan

This module is flagged as a "core module" for thorough coverage — Module 3/4/5 correctness depends on its
invariants holding.

**Unit**
- Adding a tenant to a flat with an existing active tenant raises `409 ONE_ACTIVE_TENANT` (service-layer test,
  mocked DB row lock, asserts no insert attempted).
- `TenantCreate` validation: `lease_end < lease_start` raises a `ValueError` at the Pydantic model level (before
  hitting the DB).
- `vacate_tenant` service function: called without `occupancy_status` raises a validation error at the schema
  layer (never reaches the transition logic).
- `FlatOwnershipUpdate` transactional primary-contact flip: unit test that setting a new primary contact
  atomically clears the previous row's flag within the same DB transaction (no window where two rows are both
  `true`, verified via a savepoint/rollback test or `SELECT COUNT(*)` assertion post-commit).
- Owner contact-update schema: a payload containing `full_name` submitted under `MANAGE_OWN_FLAT` scope is
  rejected by the `OwnerContactUpdate` schema (extra fields forbidden — `model_config = ConfigDict(extra="forbid")`).

**Integration** (FastAPI TestClient + test DB/transaction rollback per test)
- `POST /api/v1/towers/{tower_id}/flats` with a duplicate active `flat_number` in the same tower returns `409`
  (unique index violation mapped to a clean error, not a raw DB traceback).
- `POST .../tenants` with `lease_start > lease_end` returns `422` with a `field_errors` entry for `lease_end`.
- `POST .../tenants/{id}/vacate` with `occupancy_status=vacant` persists exactly `vacant` on the flat row — assert
  via a follow-up `GET`, not just the response body, to catch a bug where the code defaults to `owner_occupied`.
- `POST .../tenants` on a flat that already has an active tenant returns `409 ONE_ACTIVE_TENANT` and the DB still
  has exactly one row with `is_active=true` for that flat afterward.
- A request authenticated as a Flat Owner (JWT scoped to `MANAGE_OWN_FLAT`, no `MANAGE_RESIDENTS`) attempting
  `PUT .../flats/{flat_id}` with a changed `carpet_area` is rejected, but the same token successfully
  `POST`s/`PATCH`es a tenant record for their own flat.
- A Flat Owner token attempting to act on a flat they do **not** own (valid flat in a tower they have no
  `FlatOwnership` row for) receives `403`/`404` on every route in this module, including `GET`.
- `.../owners/{ownership_id}/remove` on the sole active owner of a flat returns `409 LAST_OWNER_ON_FLAT`.
- `.../owners/{ownership_id}/remove` on the primary contact with co-owners present, without
  `new_primary_owner_id`, returns `409 PRIMARY_CONTACT_REQUIRED`; with a valid `new_primary_owner_id`, succeeds and
  the new owner's row now has `is_primary_contact=true`.
- `.../deactivate` on a flat with a `pending`/`overdue` due (seeded via Module 3 fixtures) returns
  `409 OPEN_DUES_EXIST`; on a flat with no open dues, succeeds and sets `deactivated_at`.
- Concurrency test: two simultaneous `POST .../tenants` requests against the same flat (fired in parallel via
  `asyncio.gather` against the test client) result in exactly one success and one `409` — proves the row lock
  actually serializes the race, not just the happy-path pre-check.

**What must NOT break (regression list)**
- Ownership history rows (`flat_ownerships`) are never hard-deleted or overwritten — "removing" a co-owner always
  sets `date_to`, never deletes the row.
- Tenant history rows (`tenants` with `is_active=false`) are never hard-deleted — vacating always preserves the
  row; only genuine data-entry corrections use `deactivated_at`, and that distinction must remain visible/queryable.
- A flat can never end up with more than one `is_active=true` tenant, nor more than one currently-active
  `is_primary_contact=true` ownership row — both DB partial unique indexes must remain in every migration.
- `occupancy_status` is only ever changed by the tenant-create/vacate service functions (or admin's explicit flat
  edit for edge corrections) — no other code path (e.g. a future bulk-import script) should write to this column
  directly without going through the same transactional invariant checks.
- Owner and Tenant identity fields (`full_name`, `id_number`) remain admin-only (`MANAGE_RESIDENTS`); a regression
  that allows `MANAGE_OWN_FLAT` to change them is a security regression, not just a bug.
- Cross-tower isolation: an Owner record spanning multiple towers must never leak one tower's flat/tenant data to
  a request scoped to another tower — every list/detail route re-validates `tower_id` against the caller's access
  even though `Owner` itself is a global table.
