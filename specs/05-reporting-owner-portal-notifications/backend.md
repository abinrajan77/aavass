# Module 5 — Backend

> FastAPI routers, Pydantic schemas, and the (minimal) new tables this module owns. Everything else — `Flat`, `Owner`, `FlatOwnership`, `Tenant` (Module 2; tenant history is **non-active rows of the single `tenants` table**, there is no separate `TenantHistory` table — see `../02-flat-owner-tenant/overview.md`), `MaintenanceDue`, `BillingCycle`, the shared `Payment`/`Receipt` tables (Module 3, `due_type`-discriminated and reused by Module 4), `SpecialCollectionDue`, `SpecialCollection`, `Expenditure` (Module 4), `require_permission`, `audit_log` (Module 1) — is read-only input to this module. Follow `../00-architecture-and-standards.md` §6 API conventions throughout (offset pagination envelope, RFC7807 errors, tower-scoped routing, `require_permission` dependency).

## 1. New data model (this module's only owned tables)

This module is primarily a read/aggregation layer. It owns exactly two small tables:

```sql
-- Draft notification message templates (v1.0 manual notification support, PRD §8.1)
CREATE TABLE notification_templates (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type      TEXT NOT NULL CHECK (event_type IN ('due_generated', 'overdue_reminder', 'payment_confirmed')),
    recipient_role  TEXT NOT NULL CHECK (recipient_role IN ('resident', 'owner_copy')),
    channel         TEXT NOT NULL DEFAULT 'generic', -- 'generic' in v1.0; 'sms'/'whatsapp' reserved for v1.1 per-channel variants
    template_text   TEXT NOT NULL, -- e.g. "Dear {resident_name}, your maintenance due of Rs. {amount} for {flat_number}, {tower_name} for {period} is now due on {due_date}."
    is_active       BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (event_type, recipient_role, channel)
);
-- Seeded at migration time with one row per (event_type, recipient_role) combination; v1.0 admin cannot edit
-- template text via UI (no requirement for it) but the table is designed so a future admin-editable
-- template screen needs no schema change.

-- Async export job tracking for large (>5000 row) report exports (see cloud.md for the SQS pattern)
CREATE TABLE export_jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tower_id        UUID NOT NULL REFERENCES towers(id),
    report_type     TEXT NOT NULL CHECK (report_type IN (
                        'collection', 'outstanding_dues', 'expenditure',
                        'collection_vs_expenditure', 'tenant_register')),
    format          TEXT NOT NULL CHECK (format IN ('pdf', 'csv')),
    params          JSONB NOT NULL,          -- period/date-range/billing_cycle_id etc., the natural key for idempotency
    status          TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'done', 'failed')),
    row_count       INTEGER,
    file_s3_key     TEXT,                    -- set when status = 'done'
    error_message   TEXT,                    -- set when status = 'failed'
    requested_by    UUID NOT NULL REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at    TIMESTAMPTZ
);
CREATE INDEX ix_export_jobs_tower_status ON export_jobs (tower_id, status);
```

No other tables are created. `notification_templates` has no `tower_id` — templates are global text with placeholders; tower/flat-specific values are substituted at request time from Module 2/3/4 data, never stored per-tower.

## 2. Report endpoints

All under `/api/v1/towers/{tower_id}/reports/...`, guarded by `require_permission("VIEW_REPORTS")` (Admin only in v1.0 — flat owners do not hold `VIEW_REPORTS`, they use the separate owner-portal endpoints in §3). Every report endpoint accepts `format` as a query param; omitting it returns JSON (used by the frontend preview table before export).

### 2.1 `GET /api/v1/towers/{tower_id}/reports/collection`

Query params: `billing_cycle_id` (UUID, required), `format` (`pdf`|`csv`, optional).

```python
class CollectionReportRow(BaseModel):
    flat_number: str
    owner_names: list[str]
    resident_type: Literal["owner", "tenant"]
    resident_name: str
    amount_due: Decimal
    status: Literal["paid", "pending", "overdue"]
    payment_date: date | None
    payment_mode: Literal["cash", "bank_transfer", "cheque"] | None
    reference_number: str | None
    receipt_number: str | None

class CollectionReportResponse(BaseModel):
    tower_id: UUID
    billing_cycle_id: UUID
    billing_month: int
    billing_year: int
    generated_at: datetime
    items: list[CollectionReportRow]
    totals: dict[str, Decimal]  # {"total_due": ..., "total_paid": ..., "total_pending": ..., "total_overdue": ...}
```

Source: `maintenance_dues` joined to `flats`, `flat_ownerships` (active), the resident (tenant if `flats.occupancy_status = 'tenant_occupied'` else primary owner), and `payments`/`receipts` (left join `ON payments.due_type = 'maintenance' AND payments.due_id = maintenance_dues.id`, per the shared-table shape in `../03-maintenance-billing/backend.md` §1.5) where present, filtered by `billing_cycle_id`.

### 2.2 `GET /api/v1/towers/{tower_id}/reports/outstanding-dues`

Query params: `as_of_date` (date, optional, defaults to today), `format`.

```python
class OutstandingDueRow(BaseModel):
    flat_number: str
    due_type: Literal["maintenance", "special_collection"]
    owner_names: list[str]
    resident_name: str
    amount_due: Decimal
    due_date: date
    grace_period_days: int  # grace period effective at the due's generation, not the tower's current setting
    days_overdue: int       # (as_of_date - (due_date + grace_period_days)), floor 0

class OutstandingDuesReportResponse(BaseModel):
    tower_id: UUID
    as_of_date: date
    items: list[OutstandingDueRow]
    total_outstanding: Decimal
```

Source: `maintenance_dues` UNION `special_collection_dues` where `status = 'overdue'`.

### 2.3 `GET /api/v1/towers/{tower_id}/reports/expenditure`

Query params: `period_start` (date, required), `period_end` (date, required), `format`.

```python
class ExpenditureReportRow(BaseModel):
    date: date
    category: Literal["cleaning", "security", "repairs", "utilities", "other"]
    description: str
    vendor_payee: str
    amount: Decimal
    payment_mode: str
    has_attachment: bool

class CategoryTotal(BaseModel):
    category: str
    total: Decimal

class ExpenditureReportResponse(BaseModel):
    tower_id: UUID
    period_start: date
    period_end: date
    items: list[ExpenditureReportRow]
    category_totals: list[CategoryTotal]
    grand_total: Decimal
```

### 2.4 `GET /api/v1/towers/{tower_id}/reports/collection-vs-expenditure`

Query params: `period_type` (`month`|`financial_year`, required), `month` (1-12, required if `period_type=month`), `year` (required), `format`. Financial year = Apr 1–Mar 31 (India convention, matches PRD's INR/Indian association context) when `period_type=financial_year`.

```python
class CollectionVsExpenditureResponse(BaseModel):
    tower_id: UUID
    period_label: str  # e.g. "June 2026" or "FY 2025-26"
    maintenance_collected: Decimal
    special_collection_collected: Decimal
    total_collected: Decimal
    total_expenditure: Decimal
    net: Decimal  # total_collected - total_expenditure
    expenditure_by_category: list[CategoryTotal]
```

**This is the most complex report — exact SQL-level aggregation approach:**

```sql
-- Collections: Module 3's `payments` table is already a single shared table for both maintenance and
-- special-collection payments, discriminated by `due_type` (see ../03-maintenance-billing/backend.md
-- §1.5) — no UNION across two payments tables is needed; `due_type` itself is the source tag, and
-- `payments.tower_id` (denormalized on that table) lets this query filter without joining either due
-- table at all. Totals never double count because `UNIQUE (due_type, due_id)` on `payments` guarantees
-- at most one payment row per due, and a due exists in exactly one due_type's table.
WITH collections AS (
    SELECT due_type AS source, amount_received, payment_date
    FROM payments
    WHERE tower_id = :tower_id
      AND payment_date BETWEEN :period_start AND :period_end
),
expenditure_totals AS (
    SELECT category, COALESCE(SUM(amount), 0) AS category_total
    FROM expenditures
    WHERE tower_id = :tower_id
      AND expenditure_date BETWEEN :period_start AND :period_end
    GROUP BY category
)
SELECT
    (SELECT COALESCE(SUM(amount_received), 0) FROM collections WHERE source = 'maintenance')        AS maintenance_collected,
    (SELECT COALESCE(SUM(amount_received), 0) FROM collections WHERE source = 'special_collection')  AS special_collection_collected,
    (SELECT COALESCE(SUM(category_total), 0) FROM expenditure_totals)                                AS total_expenditure;
-- expenditure_by_category is the expenditure_totals CTE rows returned separately in the same query/transaction.
```

Note: `payments.payment_date` (when money was actually received), not `maintenance_dues.due_date`, is the period-membership field for collections — a due generated in one month but paid in the next is correctly attributed to the month it was actually collected. This must match how Module 3's own dashboards attribute collections, to avoid this report disagreeing with Module 3's numbers.

### 2.5 `GET /api/v1/towers/{tower_id}/reports/tenant-register`

Query params: `format` only (no period — this is a point-in-time register of all tenancy, per PRD §6.7).

```python
class TenantRegisterRow(BaseModel):
    flat_number: str
    tenant_name: str
    phone_number: str
    email: str | None
    lease_start: date
    lease_end: date | None
    is_current: bool

class TenantRegisterResponse(BaseModel):
    tower_id: UUID
    items: list[TenantRegisterRow]  # ordered by flat_number, then lease_start
```

Source: Module 2's `tenants` table for every flat in the tower — `is_current = tenants.is_active`, both current (`is_active=true`) and past (`is_active=false`) rows in a single query (no `UNION`, since there is only one physical table), ordered `flat_number, lease_start`.

### 2.6 Export flow (all 5 report endpoints, shared logic)

- Backend estimates row count for the requested filter before rendering.
- If `row_count <= 5000`: render PDF (WeasyPrint/ReportLab) or CSV synchronously and stream the file, target p50 2s / p95 10s per `00-architecture-and-standards.md` §4.
- If `row_count > 5000`: insert an `export_jobs` row (`status='pending'`), enqueue a message on the `report-export-jobs` SQS queue (payload: `job_id`, `report_type`, `tower_id`, `format`, `params`), return `202 Accepted` with `{"job_id": "..."}`. Frontend polls the **shared canonical job-status route** `GET /api/v1/towers/{tower_id}/jobs/{job_id}` (per `../06-cloud-devops.md` §4 — the same route Modules 3 and 4 poll for their own job types, `job_type="report_export"` for this module's jobs) → `{"status": "pending|running|done|failed", "result": {"download_url": "..."}}` (pre-signed S3 GET URL once `done`, per `06-cloud-devops.md` §5 pattern).

## 3. Owner self-service portal endpoints

Guarded by an "authenticated flat-owner user" dependency (not `require_permission`, since owners aren't `association_members`/role-based per `00-architecture-and-standards.md` §5.2 — they carry implicit `VIEW_TOWER_DATA` + `MANAGE_OWN_FLAT`). The dependency resolves the current user's **active** `FlatOwnership` rows (`date_to IS NULL`) and rejects any `flat_id`/`tower_id` not in that set with `403`.

### 3.1 `GET /api/v1/owners/me/flats-summary`

> **Not the same endpoint as Module 2's `GET /api/v1/me/flats`.** Module 2 owns and serves the base
> cross-tower list of flats a user currently owns (`../02-flat-owner-tenant/backend.md`) — that endpoint
> has no knowledge of dues/payments and returns quickly against Module 2's tables alone. This module
> builds a distinct, additively-named endpoint that calls Module 2's service internally and enriches
> each flat with `current_due_status` sourced from Module 3/4 — a read/aggregation step Module 2
> deliberately does not do itself (see `../02-flat-owner-tenant/backend.md` "Cross-module read
> contract"). The owner-portal frontend (§Frontend Plan) calls **this** endpoint, not Module 2's, since
> it needs the due-status badge per flat; Module 1's post-login redirect logic (which only needs the
> flat/tower list to route to a tower context) calls Module 2's simpler endpoint. Do not merge these or
> point the frontend at the wrong one.

No path params — scoped entirely to the authenticated user.

```python
class OwnedFlatSummary(BaseModel):
    flat_id: UUID
    tower_id: UUID
    tower_name: str
    flat_number: str
    occupancy_status: Literal["owner_occupied", "tenant_occupied", "vacant"]
    is_primary_owner: bool
    current_due_status: Literal["paid", "pending", "overdue", "no_active_due"]

class OwnedFlatsResponse(BaseModel):
    towers: list[dict]  # [{"tower_id": ..., "tower_name": ..., "flats": [OwnedFlatSummary, ...]}]
```

Grouped by tower so the frontend Command-palette switcher can render tower → flats directly. This is the only endpoint that spans towers for an owner — every other owner endpoint below is single-flat/single-tower scoped.

### 3.2 `GET /api/v1/owners/me/flats/{flat_id}/dashboard`

```python
class OwnerFlatDashboardResponse(BaseModel):
    flat_id: UUID
    tower_id: UUID
    flat_number: str
    current_due: CollectionReportRow | None       # this cycle's due, null if none generated yet
    payment_history: list[CollectionReportRow]     # all past dues for this flat, most recent first
    receipts: list[dict]                           # [{"receipt_id", "receipt_number", "billing_period", "download_url"}]
    tower_expenditures: list[ExpenditureReportRow] # current FY, read-only
    tenant_history: list[TenantRegisterRow]        # this flat only, current + past
    ytd_totals: dict[str, Decimal]                 # {"total_due_ytd": ..., "total_paid_ytd": ...} — backs the frontend NumberTicker stats
```

`flat_id` must be in the caller's active ownership set (§3 dependency) — otherwise `403 OWNERSHIP_NOT_FOUND`, regardless of whether the flat exists.

## 4. Notification template preview endpoint

### `GET /api/v1/notifications/templates/preview`

Query params: `event` (`due_generated`|`overdue_reminder`|`payment_confirmed`, required), `due_id` (UUID, required), `due_type` (`maintenance`|`special_collection`, required — disambiguates which table `due_id` refers to). Guarded by `require_permission("VIEW_REPORTS")` (admin-only; not exposed to owners — drafting/copying messages is an admin action per PRD §8.1).

```python
class NotificationMessage(BaseModel):
    recipient: Literal["tenant", "owner"]
    recipient_name: str
    recipient_phone: str
    message_text: str  # fully rendered, placeholders substituted

class NotificationPreviewResponse(BaseModel):
    event: Literal["due_generated", "overdue_reminder", "payment_confirmed"]
    due_id: UUID
    flat_number: str
    messages: list[NotificationMessage]  # 1 item if owner-occupied, 2 items (tenant + owner_copy) if tenant-occupied
```

Logic:
1. Resolve the due (Module 3 `maintenance_dues` or Module 4 `special_collection_dues` per `due_type`) and its flat/resident/owner via Module 2.
2. Look up `notification_templates` for `(event_type=event, recipient_role='resident')`; render placeholders (`{resident_name}`, `{flat_number}`, `{tower_name}`, `{amount}`, `{due_date}`, `{period}` as applicable) against the resolved due/flat data.
3. If `flats.occupancy_status = 'tenant_occupied'`, additionally render `(event_type=event, recipient_role='owner_copy')` for the primary owner and append it — always two messages for tenant-occupied flats, per PRD §8.1 and the acceptance criteria in `overview.md`.
4. Response contains no send/dispatch action and no delivery-status field — this endpoint only prepares text for admin to copy.

## Backend Test Plan

- **Integration**: outstanding dues report includes only `Overdue`-status dues (not `Pending`), and `days_overdue` for a due with `due_date=2026-06-01`, `grace_period_days=5` computed as of `2026-06-10` equals 4 (10 − (1+5)).
- **Integration**: outstanding dues report uses the grace period value stored on the due at generation time, not the tower's current grace period setting — verified by changing the tower's grace period after due generation and confirming the report's `days_overdue` is unaffected.
- **Integration**: tenant register report includes both current (`is_current=true`) and past (`is_current=false`) tenants across all flats in the tower, ordered by `flat_number` then `lease_start` ascending.
- **Integration**: collection vs expenditure summary for a month with maintenance payments, special-collection payments, and expenditures all present reconciles: `total_collected == maintenance_collected + special_collection_collected`, and each equals the independently-queried sum from Module 3/4's own tables for that period — no double counting.
- **Integration**: collection vs expenditure summary for a month with zero expenditures returns `total_expenditure = 0` and `expenditure_by_category = []`, HTTP `200` — not an error.
- **Integration**: monthly collection report's `total_paid` matches the sum of `Payment.amount_received` for that `billing_cycle_id` queried directly against Module 3's tables.
- **Integration**: `/owners/me/flats-summary` never returns a flat where the caller's `FlatOwnership.date_to` is set (sold flat) — confirmed by creating an ownership, closing it, and asserting the flat drops out of the list on the next call, with no `include_history` flag able to bring it back (no such flag exists in v1.0).
- **Integration**: `/owners/me/flats/{flat_id}/dashboard` for a flat the caller does not own (never owned, or previously owned) returns `403`, never `404` (avoids leaking flat existence) and never partial data.
- **Integration**: owner dashboard `tenant_history` for a flat that changed ownership includes tenancy periods that predate the current owner's purchase, sourced from Module 2's `tenants` table (its historical, `is_active=false` rows), confirming the audit trail survives ownership transfer even though portal *access* does not.
- **Integration**: report export request whose filter resolves to >5000 rows returns `202` with a `job_id`, inserts an `export_jobs` row with `status='pending'`, and does not block past ~1s; a request resolving to ≤5000 rows returns the file synchronously.
- **Integration**: a duplicate/retried export request with identical `(tower_id, report_type, format, params)` while a prior job is still `pending`/`running` does not enqueue a second SQS message (idempotency check against `export_jobs`, mirroring the natural-key pattern in `06-cloud-devops.md` §4).
- **Unit**: notification template rendering for a tenant-occupied flat's `due_generated` event produces exactly two `NotificationMessage` objects (`recipient=tenant`, `recipient=owner`) with correctly substituted placeholders; for an owner-occupied flat, exactly one (`recipient=owner`).
- **Unit**: notification preview for a due with a missing/null resident (defensive case) raises a `422` rather than rendering a message with blank placeholders.
- **Unit**: PDF/CSV renderers produce column-identical output for the same report (CSV headers match PDF table headers) for all 5 report types.

**What must NOT break:**
- No double-counting income across reports — a single `Payment` row must never be summed into `total_collected` twice (e.g. once via `maintenance_dues` join, once via a stray join to `special_collection_dues`); the UNION ALL branches in §2.4 must remain mutually exclusive by construction (a due row exists in exactly one of the two due tables).
- Report totals must always reconcile with Module 3/4's own source-of-truth tables — this module must never introduce a parallel/cached running total that can drift; every report query reads `payments`/`expenditures` directly at request time (or at job-run time for async exports), never a pre-computed snapshot that could go stale.
- Owner-portal scoping must never leak another owner's or another tower's data, even transiently — every owner endpoint re-validates active `FlatOwnership` server-side on every request (per `00-architecture-and-standards.md` §5.3), never trusting a `flat_id`/`tower_id` from a prior response or client-side cache.
- Immutable/paid records (per `00-architecture-and-standards.md` §6) must never be mutated by this module — it is read-only against Module 3/4 tables; if a report needs a field that isn't there, add it in the owning module's migration, not by writing into those tables from Module 5.
