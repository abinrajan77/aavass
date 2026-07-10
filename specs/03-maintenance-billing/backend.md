# Module 3 — Maintenance Billing — Backend

> Follows API conventions from `../00-architecture-and-standards.md` §6 (routing, pagination envelope, error format, audit log, soft delete/immutability) and infra patterns from `../06-cloud-devops.md` §4 (SQS) and §5 (S3). RBAC guard is `require_permission(...)` from Module 1, permissions used: `CONFIGURE_BILLING`, `CREATE_BILLING_CYCLE`, `RECORD_PAYMENT`.
>
> This module reads (never writes) `Flat`, `Owner` (incl. `is_primary_contact`), `Tenant` from Module 2 via its service layer / `GET /api/v1/towers/{tower_id}/flats` (returns `occupancy_status`, current resident, primary owner).

## 1. Data model (SQLAlchemy 2.x, async)

All tables use `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`, `created_at TIMESTAMPTZ NOT NULL DEFAULT now()` unless noted. Money columns are `NUMERIC(12,2)`.

### 1.1 `maintenance_formulas` (versioned, insert-only)

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `tower_id` | UUID FK → `towers.id` | not null |
| `base_amount` | NUMERIC(12,2) | not null, `>= 0` |
| `per_sqft_rate` | NUMERIC(12,2) | not null, `>= 0` |
| `effective_from` | DATE | not null |
| `created_by` | UUID FK → `association_members.id` | not null |
| `created_at` | TIMESTAMPTZ | |

- No `updated_at`, no `UPDATE`/`DELETE` — a "change" is always a new row. `UNIQUE (tower_id, effective_from)`.
- "Current formula" for a tower at date `d` = row with `tower_id = :tower_id AND effective_from <= :d ORDER BY effective_from DESC LIMIT 1`.

### 1.2 `grace_period_configs` (versioned, insert-only)

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `tower_id` | UUID FK → `towers.id` | not null |
| `grace_period_days` | INTEGER | not null, `>= 0` |
| `effective_from` | DATE | not null |
| `created_by` | UUID FK → `association_members.id` | not null |
| `created_at` | TIMESTAMPTZ | |

- Same versioning pattern as the formula. `UNIQUE (tower_id, effective_from)`. Every tower gets a seed row (`grace_period_days = 0`) when the tower is created (Module 1 responsibility, FK-only dependency here).

### 1.3 `billing_cycles`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `tower_id` | UUID FK → `towers.id` | not null |
| `month` | SMALLINT | not null, `1..12` |
| `year` | SMALLINT | not null |
| `due_date` | DATE | not null |
| `formula_id` | UUID FK → `maintenance_formulas.id` | not null — snapshot of formula used |
| `grace_period_days_snapshot` | INTEGER | not null — copied value, not a FK, so it survives even if the config row model changes |
| `status` | ENUM(`generating`, `active`) | not null, default `generating` |
| `job_id` | UUID NULLABLE | set when generation is async (see §4) |
| `created_by` | UUID FK → `association_members.id` | not null |
| `created_at` | TIMESTAMPTZ | |

- `UNIQUE (tower_id, month, year)` — this is the idempotency guarantee at the DB level, matching the SQS idempotency key in `06-cloud-devops.md` §4.
- Immutability rule: once `status = 'active'` (i.e., at least one `maintenance_dues` row exists for it — in practice these transition together in the same transaction/job), `PUT`/`DELETE` return `409 IMMUTABLE_RECORD`. A `status = 'generating'` cycle with zero dues (mid-flight async job) may still be cancelled/edited — this is the only window where mutation is allowed.

### 1.4 `maintenance_dues`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `billing_cycle_id` | UUID FK → `billing_cycles.id` | not null |
| `tower_id` | UUID FK → `towers.id` | not null, denormalized from `billing_cycle_id` at insert time — required (not optional) so list/dashboard queries never need to join through `billing_cycles` to filter by tower, per the 200ms/400ms list-query and 250ms/500ms dashboard-aggregate budgets in `../00-architecture-and-standards.md` §4 |
| `flat_id` | UUID FK → `flats.id` (Module 2) | not null |
| `amount` | NUMERIC(12,2) | not null — computed at generation time, frozen thereafter |
| `carpet_area_snapshot` | NUMERIC(10,2) | not null — for audit/display even if flat area is edited later |
| `assigned_to_type` | ENUM(`tenant`, `owner`) | not null |
| `assigned_to_id` | UUID | not null — `tenant.id` or `owner.id` depending on type; frozen at generation, never re-derived |
| `assigned_to_name_snapshot` | VARCHAR(200) | not null — resident's display name at generation time, so history reads correctly even if the person record changes later |
| `primary_owner_id_snapshot` | UUID FK → `owners.id` | not null — always captured regardless of `assigned_to_type`, used for receipts |
| `due_date` | DATE | not null — copied from cycle for indexing |
| `status` | ENUM(`pending`, `paid`, `overdue`) | not null, default `pending` |
| `created_at` | TIMESTAMPTZ | |

- `UNIQUE (billing_cycle_id, flat_id)` — one due per flat per cycle.
- Index: `(tower_id, status, due_date)`.
- No `UPDATE` to `amount`, `assigned_to_*`, `due_date` ever, by any endpoint — only `status` transitions (`pending → overdue`, `pending/overdue → paid`).

### 1.5 `payments` — shared table, also used by Module 4 for special-collection payments

> **Canonical cross-module contract.** This table (and `receipts`/`record_payment()` below) is shared
> infrastructure: Module 4's special-collection dues are paid and receipted through this exact same
> table via a `due_type` discriminator, per `../00-architecture-and-standards.md` §7 and
> `../04-special-collections-expenditure/backend.md` "Reuse of Module 3 payment/receipt flow." There is
> no separate `special_collection_payments` table — do not create one.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `tower_id` | UUID FK → `towers.id` | not null — lets Module 4 (and Module 5's reports) query/filter without joining through either due table |
| `due_type` | ENUM(`maintenance`, `special_collection`) | not null — discriminator; determines which table `due_id` is resolved against at the application layer |
| `due_id` | UUID | not null — **no DB-level FK** (polymorphic: `maintenance_dues.id` when `due_type='maintenance'`, `special_collection_dues.id` — a Module 4 table — when `due_type='special_collection'`); existence/ownership is validated in the service layer, not by a database constraint |
| `payment_date` | DATE | not null |
| `amount_received` | NUMERIC(12,2) | not null, `> 0` |
| `payment_mode` | ENUM(`cash`, `bank_transfer`, `cheque`) | not null |
| `reference_number` | VARCHAR(100) | nullable |
| `recorded_by` | UUID FK → `association_members.id` | not null |
| `created_at` | TIMESTAMPTZ | |

- `UNIQUE (due_type, due_id)` — one payment per due, regardless of due type (no partial payments).

### 1.6 `receipts` — shared table, also used by Module 4

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `tower_id` | UUID FK → `towers.id` | not null |
| `due_type` | ENUM(`maintenance`, `special_collection`) | not null — denormalized copy from `payments`, for query convenience |
| `due_id` | UUID | not null — same polymorphic pattern as `payments.due_id`, no DB-level FK |
| `payment_id` | UUID FK → `payments.id` | not null, `UNIQUE` |
| `receipt_number` | VARCHAR(30) | not null, `UNIQUE` — format `{tower_code}-{year}-{seq:06d}`, sequential **per tower**, shared across `due_type` (one numbering sequence per tower, not one per due type). `tower_code` is `towers.code` (see `../01-auth-rbac-tower-setup/backend.md` §"Tower table" — a short unique code added to `Tower` specifically to support this) |
| `owner_name_snapshot` | VARCHAR(200) | not null — primary owner's name at time of receipt generation |
| `billing_period_label` | VARCHAR(100) | not null — e.g. `"July 2026"` for a maintenance due, or `"Special Collection: {title}"` for a special-collection due (the one due-type-specific piece of the receipt template, per Module 4's `backend.md`) |
| `pdf_s3_key` | VARCHAR(300) | not null — `receipts/{tower_id}/{receipt_id}.pdf` |
| `generated_at` | TIMESTAMPTZ | |

### 1.7 `receipt_counters` (per-tower sequential numbering)

| Column | Type | Notes |
|---|---|---|
| `tower_id` | UUID PK, FK → `towers.id` | |
| `next_number` | INTEGER | not null, default 1 |

Incrementing this row happens with `SELECT ... FOR UPDATE` in the same DB transaction as the `receipts` insert, to guarantee no gaps/collisions under concurrent mark-paid calls for the same tower.

## 2. Formula calculation logic

```python
from decimal import Decimal, ROUND_HALF_UP

def calculate_monthly_maintenance(base_amount: Decimal, per_sqft_rate: Decimal, carpet_area: Decimal) -> Decimal:
    area_component = (carpet_area * per_sqft_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return (base_amount + area_component).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
```

`Monthly Maintenance = Base Amount + (Carpet Area × Per Sq Ft Rate)`, per PRD §6.3.1. This is called once per flat during billing-cycle generation, never recomputed after — the result is stored in `maintenance_dues.amount`.

## 3. Overdue transition — design decision

**Chosen approach: a daily scheduled job**, not an on-read computed check.

Rationale:
- List/dashboard reads (dues list, dashboard stat cards) must meet the 200ms/400ms p95 list-query budget and the 250ms/500ms dashboard-aggregate budget in `00-architecture-and-standards.md` §4. A persisted `status` column lets those queries do a plain indexed `WHERE status = 'overdue'` filter/count; computing overdue-ness on every read (join against `grace_period_configs`, date math, per-row) would add CPU cost to every single list/dashboard request instead of once a day.
- The transition is also a financial-state change that must appear in `audit_log` (PRD §7 Auditability) — a job gives one clear place to write those audit rows; an on-read check would either skip auditing the transition entirely or require writing on every GET, which is the wrong place to mutate state.
- The business rule ("due_date + grace_period_days has passed") only needs day-granularity freshness — PRD's own example is in days, not hours — so a nightly job fully satisfies "the day after the due date" semantics without needing real-time computation.

Implementation:
```python
def is_overdue(due_date: date, grace_period_days: int, as_of: date) -> bool:
    return as_of > due_date + timedelta(days=grace_period_days)
```
- Runs as a Celery beat / APScheduler cron job at `00:15 UTC` daily (worker process defined in `06-cloud-devops.md` §3/§4 infra, same ECS worker service used for SQS-backed jobs).
- Query: `UPDATE maintenance_dues SET status = 'overdue' WHERE status = 'pending' AND due_date + (grace_period_days_snapshot_from_cycle) * INTERVAL '1 day' < CURRENT_DATE` (grace period read from the due's `billing_cycle.grace_period_days_snapshot`, i.e. the value frozen at that cycle's generation — never the tower's current config).
- Each flip writes one `audit_log` row per due (`action = 'due_overdue_transition'`) or a single batched summary row referencing the affected due IDs — pick per-row for full auditability given this is a CORE financial module.
- `is_overdue()` is unit-testable in isolation from the scheduler (see Test Plan §6.1).
- Marking a due Paid is allowed regardless of whether the nightly job has already flipped it to `Overdue` — Overdue is a label on lateness, not a block on payment.

## 4. Async job trigger — billing-cycle generation

Per `00-architecture-and-standards.md` §4 ("Bulk write — billing cycle generation ... 5s sync for ≤300 flats; async job + polling/webhook beyond that") and `06-cloud-devops.md` §4:

```python
@router.post("/api/v1/towers/{tower_id}/billing-cycles", status_code=201)
async def create_billing_cycle(tower_id: UUID, payload: BillingCycleCreate, ...):
    active_flat_count = await flats_service.count_active(tower_id)  # Module 2 read
    cycle = await create_cycle_row(tower_id, payload, status="generating")  # unique (tower_id, month, year) enforced here -> 409 if exists
    if active_flat_count <= 300:
        await generate_dues_sync(cycle.id)   # same request/transaction, <=5s budget
        cycle.status = "active"
        return 201, BillingCycleOut.from_orm(cycle)
    else:
        job_id = await sqs.enqueue(
            queue="billing-cycle-jobs",
            payload={"tower_id": str(tower_id), "cycle_id": str(cycle.id), "month": payload.month, "year": payload.year},
            idempotency_key=f"{tower_id}:{payload.month}:{payload.year}",
        )
        cycle.job_id = job_id
        return 202, {"cycle_id": cycle.id, "job_id": job_id, "status": "generating"}
```

- Worker consumes `billing-cycle-jobs`, generates one `maintenance_dues` row per active flat (formula calc from §2, assignment logic from §5), then flips `billing_cycles.status = 'active'` in one transaction. A retried/duplicate SQS message for the same `tower_id+month+year` is a safe no-op because the unique constraint on `billing_cycles` already exists and dues generation is itself keyed on `(billing_cycle_id, flat_id)` unique.
- Frontend polls the **shared canonical job-status route** `GET /api/v1/towers/{tower_id}/jobs/{job_id}` (per `06-cloud-devops.md` §4 — one polling route/hook for every module's async jobs, not a module-specific path) until `done`, then loads the dues list.

## 5. Due assignment logic (at generation time, sync or async — same code path)

```python
async def assign_due(flat: FlatRead) -> tuple[str, UUID, str]:
    # flat.occupancy_status, flat.current_tenant, flat.primary_owner come from Module 2's flat read model
    if flat.occupancy_status == "tenant_occupied" and flat.current_tenant is not None:
        return "tenant", flat.current_tenant.id, flat.current_tenant.full_name
    if flat.primary_owner is None:
        raise DueGenerationError(flat_id=flat.id, reason="NO_PRIMARY_OWNER")  # per-flat failure, does not abort whole cycle
    return "owner", flat.primary_owner.id, flat.primary_owner.full_name
```
`primary_owner_id_snapshot` is always set to `flat.primary_owner.id` regardless of branch taken (needed for receipts even when `assigned_to_type = 'tenant'`).

## 6. Routers

All routes require an authenticated session; permission checks via `require_permission(...)` dependency (Module 1). All list endpoints return the standard pagination envelope (`00-architecture-and-standards.md` §6). All errors use the shared `{error_code, message, field_errors}` shape.

### 6.1 Maintenance formula — `require_permission("CONFIGURE_BILLING")` for writes, `VIEW_TOWER_DATA`/tower membership for reads

| Method | Path | Payload / Query | Response |
|---|---|---|---|
| `POST` | `/api/v1/towers/{tower_id}/maintenance-formula` | `{ "base_amount": 2000.00, "per_sqft_rate": 0.00, "effective_from": "2026-08-01" }` (`effective_from` optional, defaults to today) | `201 MaintenanceFormulaOut` |
| `GET` | `/api/v1/towers/{tower_id}/maintenance-formula` | `?page=1&page_size=25` | paginated envelope of `MaintenanceFormulaOut`, newest `effective_from` first |
| `GET` | `/api/v1/towers/{tower_id}/maintenance-formula/current` | — | `MaintenanceFormulaOut` for the version effective today (`404 NO_FORMULA_CONFIGURED` if tower has never set one) |

`POST` writes an `audit_log` row (`action="formula_changed"`, `before`=previous current version, `after`=new row) — this is a config-change audit item per `00-architecture-and-standards.md` §6.

### 6.2 Grace period — `require_permission("CONFIGURE_BILLING")` for writes

| Method | Path | Payload | Response |
|---|---|---|---|
| `POST` | `/api/v1/towers/{tower_id}/grace-period-config` | `{ "grace_period_days": 5 }` (effective_from defaults to today) | `201 GracePeriodConfigOut` |
| `GET` | `/api/v1/towers/{tower_id}/grace-period-config/current` | — | `GracePeriodConfigOut` |

`POST` writes `audit_log` (`action="grace_period_changed"`).

### 6.3 Billing cycles — `require_permission("CREATE_BILLING_CYCLE")` for writes

| Method | Path | Payload / Query | Response |
|---|---|---|---|
| `POST` | `/api/v1/towers/{tower_id}/billing-cycles` | `{ "month": 7, "year": 2026, "due_date": "2026-07-10" }` | `201 BillingCycleOut` (sync path) or `202 { "cycle_id", "job_id", "status": "generating" }` (async path, >300 flats). `409 BILLING_CYCLE_ALREADY_EXISTS` if `(tower_id, month, year)` already present. |
| `GET` | `/api/v1/towers/{tower_id}/billing-cycles` | `?page=1&page_size=25` | paginated `BillingCycleOut[]`, includes `total_dues`, `total_collected`, `pending_count`, `overdue_count` aggregates per cycle |
| `GET` | `/api/v1/towers/{tower_id}/billing-cycles/{cycle_id}` | — | `BillingCycleOut` + embedded formula/grace-period snapshot used |
| `PUT` | `/api/v1/towers/{tower_id}/billing-cycles/{cycle_id}` | `{ "due_date": "2026-07-12" }` | `200` only if `status = 'generating'` and zero dues exist; else `409 IMMUTABLE_RECORD` |
| `DELETE` | `/api/v1/towers/{tower_id}/billing-cycles/{cycle_id}` | — | always `409 IMMUTABLE_RECORD` (no hard delete of financial records, ever, per PRD §7) |

### 6.4 Dues — reads need tower membership; `mark-paid` needs `require_permission("RECORD_PAYMENT")`

All routes here are tower-scoped, per `../00-architecture-and-standards.md` §6 (no top-level `/api/v1/dues/...` routes — every module's resources nest under `/api/v1/towers/{tower_id}/...`):

| Method | Path | Payload / Query | Response |
|---|---|---|---|
| `GET` | `/api/v1/towers/{tower_id}/billing-cycles/{cycle_id}/dues` | `?status=pending|paid|overdue&page=1&page_size=25` | paginated `MaintenanceDueOut[]` |
| `GET` | `/api/v1/towers/{tower_id}/dues` | `?status=pending|overdue&page=1&page_size=25` | cross-cycle dues list for the "at a glance" dashboard view (PRD §6.3.4) |
| `GET` | `/api/v1/towers/{tower_id}/billing-dashboard-stats` | — | `{ "total_collected_this_cycle": 184500.00, "pending_count": 12, "overdue_amount": 23400.00 }` — feeds the `NumberTicker` stat cards |
| `GET` | `/api/v1/towers/{tower_id}/dues/{due_id}` | — | `MaintenanceDueOut` |
| `PATCH` | `/api/v1/towers/{tower_id}/dues/{due_id}/mark-paid` | `{ "payment_date": "2026-07-09", "amount_received": 2000.00, "payment_mode": "cash", "reference_number": null }` | `200 { due: MaintenanceDueOut, receipt: ReceiptOut }`. `409 DUE_ALREADY_PAID` if already paid. `422` if `amount_received <= 0`. Thin HTTP wrapper over `record_payment()` below with `due_type="maintenance"`. |
| `GET` | `/api/v1/towers/{tower_id}/dues/{due_id}/receipt` | — | `200 { "receipt_number": "...", "download_url": "<presigned S3 GET, 15 min expiry>" }`. `404 RECEIPT_NOT_AVAILABLE` if due not yet paid. |

## 6.5 The shared `record_payment()` service function

This is the exact integration point Module 4 depends on (see `../04-special-collections-expenditure/backend.md`
"Reuse of Module 3 payment/receipt flow") — Module 4's special-collection `mark-paid` endpoint is a thin wrapper
that calls this same function with `due_type="special_collection"`; it does not reimplement any of the logic below.

```python
async def record_payment(
    db: AsyncSession,
    *,
    tower_id: UUID,
    due_type: Literal["maintenance", "special_collection"],
    due_id: UUID,
    payment_date: date,
    amount_received: Decimal,
    payment_mode: Literal["cash", "bank_transfer", "cheque"],
    reference_number: str | None,
    recorded_by: AssociationMember,
) -> Receipt:
    # 1. Resolve the due row by due_type (maintenance_dues or Module 4's special_collection_dues),
    #    scoped to tower_id; 404 if not found in this tower, 409 DUE_ALREADY_PAID if status='paid'.
    due = await _resolve_due(db, due_type, due_id, tower_id)
    if due.status == "paid":
        raise HTTPException(409, detail={"error_code": "DUE_ALREADY_PAID"})

    # 2. Insert Payment (single transaction with everything below).
    payment = Payment(tower_id=tower_id, due_type=due_type, due_id=due_id,
                       payment_date=payment_date, amount_received=amount_received,
                       payment_mode=payment_mode, reference_number=reference_number,
                       recorded_by=recorded_by.id)
    db.add(payment)
    await db.flush()

    # 3. Transition the due's own status column to 'paid' (dispatched by due_type — this function,
    #    not Module 4's router, owns this write, even though the table itself belongs to Module 4
    #    for special_collection_dues; Module 4 grants this function the necessary DB access).
    due.status = "paid"

    # 4. Resolve billing_period_label per due_type: f"{month_name} {year}" for maintenance,
    #    f"Special Collection: {special_collection.title}" for special_collection (looked up via
    #    Module 4's special_collections table when due_type='special_collection').
    label = await _billing_period_label(db, due_type, due)

    # 5. Render PDF, upload to S3 (receipts/{tower_id}/{receipt_id}.pdf), get next receipt_number
    #    from receipt_counters (row-locked, one sequence per tower shared across due_type).
    receipt_number = await _next_receipt_number(db, tower_id)
    pdf_s3_key = await _render_and_upload_receipt(tower_id, due, payment, label, receipt_number)

    receipt = Receipt(tower_id=tower_id, due_type=due_type, due_id=due_id, payment_id=payment.id,
                       receipt_number=receipt_number, owner_name_snapshot=due.primary_owner_name,
                       billing_period_label=label, pdf_s3_key=pdf_s3_key)
    db.add(receipt)

    # 6. Audit log (action="payment_recorded"), same transaction.
    await write_audit_log(db, actor=recorded_by.user, tower_id=tower_id, action="payment_recorded",
                           entity_type=due_type, entity_id=due_id, before={"status": "pending"}, after={"status": "paid"})
    await db.commit()
    return receipt
```

`mark-paid` (both this module's and Module 4's) target: 500ms p50 / 2s p95 (`../00-architecture-and-standards.md` §4); if this later regresses past 2s in practice, move PDF generation to a background job that notifies-on-ready — but ship synchronous for v1.0.

## 7. Pydantic schemas (representative)

```python
class MaintenanceFormulaCreate(BaseModel):
    base_amount: Decimal = Field(ge=0, decimal_places=2)
    per_sqft_rate: Decimal = Field(ge=0, decimal_places=2)
    effective_from: date | None = None

class MaintenanceFormulaOut(BaseModel):
    id: UUID
    tower_id: UUID
    base_amount: Decimal
    per_sqft_rate: Decimal
    effective_from: date
    created_at: datetime

class GracePeriodConfigCreate(BaseModel):
    grace_period_days: int = Field(ge=0)

class BillingCycleCreate(BaseModel):
    month: int = Field(ge=1, le=12)
    year: int = Field(ge=2020, le=2100)
    due_date: date

class BillingCycleOut(BaseModel):
    id: UUID
    tower_id: UUID
    month: int
    year: int
    due_date: date
    status: Literal["generating", "active"]
    formula_id: UUID
    grace_period_days_snapshot: int
    total_dues: int
    total_collected: Decimal
    pending_count: int
    overdue_count: int

class MaintenanceDueOut(BaseModel):
    id: UUID
    flat_id: UUID
    flat_number: str
    amount: Decimal
    assigned_to_type: Literal["tenant", "owner"]
    assigned_to_name_snapshot: str
    due_date: date
    status: Literal["pending", "paid", "overdue"]

class MarkPaidRequest(BaseModel):
    payment_date: date
    amount_received: Decimal = Field(gt=0, decimal_places=2)
    payment_mode: Literal["cash", "bank_transfer", "cheque"]
    reference_number: str | None = Field(default=None, max_length=100)

class ReceiptOut(BaseModel):
    id: UUID
    receipt_number: str
    owner_name_snapshot: str
    generated_at: datetime
    download_url: str
```

## 8. Backend Test Plan

### 8.1 Unit tests
- `calculate_monthly_maintenance(base=2000, rate=0, area=850)` → `2000.00`.
- `calculate_monthly_maintenance(base=0, rate=2, area=850)` → `1700.00`.
- `calculate_monthly_maintenance(base=1000, rate=1.5, area=600)` → `1900.00`.
- `calculate_monthly_maintenance(base=999.995, rate=0, area=0)` → rounds half-up to `1000.00` (rounding boundary).
- `is_overdue(due_date=2026-07-10, grace_period_days=5, as_of=2026-07-15)` → `False` (still exactly at boundary).
- `is_overdue(due_date=2026-07-10, grace_period_days=5, as_of=2026-07-16)` → `True` (one day past boundary).
- `is_overdue(due_date=2026-07-10, grace_period_days=0, as_of=2026-07-10)` → `False`.
- `is_overdue(due_date=2026-07-10, grace_period_days=0, as_of=2026-07-11)` → `True`.
- `assign_due()` returns `("tenant", tenant.id, tenant.full_name)` for a tenant-occupied flat with an active tenant.
- `assign_due()` returns `("owner", owner.id, owner.full_name)` for owner-occupied and for vacant flats.
- `assign_due()` raises `DueGenerationError(NO_PRIMARY_OWNER)` when no owner on the flat has `is_primary_contact = True`.
- Receipt number formatting: sequential per tower, no gaps under 100 simulated concurrent `mark-paid` calls against the same tower (drives `receipt_counters` row-lock test, can be simulated with asyncio tasks against a test DB).

### 8.2 Integration tests
- Generating a billing cycle twice for the same `tower_id + month + year` → second call returns `409 BILLING_CYCLE_ALREADY_EXISTS`; only one `billing_cycles` row and one set of dues exists.
- `PUT` on a `billing_cycle` that already has dues → `409 IMMUTABLE_RECORD`.
- `DELETE` on any `billing_cycle` → always `409 IMMUTABLE_RECORD`, even if `status = 'generating'` with zero dues.
- Marking a due paid twice → second call returns `409 DUE_ALREADY_PAID`; exactly one `payments` row and one `receipts` row exist for that due.
- `mark-paid` with `amount_received = 0` or negative → `422` with `field_errors.amount_received` populated; no `payments`/`receipts` row created.
- Receipt for a due whose `assigned_to_type = 'tenant'` still contains the flat's primary owner's name (`owner_name_snapshot` on the `receipts` row, and in the rendered PDF text) — not the tenant's name.
- Mid-cycle tenant vacate (Module 2 marks tenant inactive / occupancy status changes) does **not** change `maintenance_dues.assigned_to_id`/`assigned_to_name_snapshot`/`assigned_to_type` for dues already generated in the current or past cycles.
- A tower with 350 active flats generating a cycle returns `202` + `job_id`; polling `GET /api/v1/towers/{tower_id}/jobs/{job_id}` eventually returns `done`, and exactly 350 `maintenance_dues` rows exist afterward, each unique on `(billing_cycle_id, flat_id)`.
- A retried/duplicate SQS message for the same `tower_id+month+year+cycle_id` does not create a second batch of dues (idempotency of the worker).
- Formula changed after a cycle was generated: re-fetching that historical cycle still reports the original `formula_id`/`base_amount`/`per_sqft_rate` it was generated with, and the dues' `amount` values are unchanged.
- Grace period changed after a cycle was generated: that cycle's `grace_period_days_snapshot` is unchanged, and overdue transition timing for its dues uses the old value, not the tower's new current grace period.
- Cross-tower isolation: a user scoped to Tower A cannot `GET`/`PATCH` a due belonging to Tower B (`403`/`404`, never leaks data).
- `audit_log` gets exactly one row for each of: formula change, grace-period change, payment recorded, and (batched or per-row) each Pending→Overdue transition.

### 8.3 What must NOT break (regression list)
- Formula/grace-period versioning must remain append-only — no migration or hotfix should ever `UPDATE` an existing `maintenance_formulas` or `grace_period_configs` row.
- `maintenance_dues.amount`, `assigned_to_type`, `assigned_to_id`, `due_date` must never be mutated by any endpoint after creation — only `status`.
- The `(tower_id, month, year)` unique constraint on `billing_cycles` must never be dropped or made non-unique — it is the sole idempotency guard for cycle generation.
- `409 IMMUTABLE_RECORD` behavior on cycles/paid dues must survive any future addition of an "edit cycle" admin convenience feature.
- Receipt PDFs must always resolve the **primary owner** name at render time from `primary_owner_id_snapshot`, never from `assigned_to_id`, even after refactors that touch the assignment logic.
- The nightly overdue job must remain idempotent (running it twice in a day must not double-log audit entries or re-flip an already-Overdue or Paid due).
