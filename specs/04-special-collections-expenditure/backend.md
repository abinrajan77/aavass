# Module 4 — Backend

FastAPI (Python 3.12), Pydantic v2, SQLAlchemy 2.x (async), Alembic — per `../00-architecture-and-standards.md` §1. All routes are tower-scoped under `/api/v1/towers/{tower_id}/...` per §6 and pass through `require_permission(...)`, which re-validates `tower_id` against the caller's accessible towers on every request.

RBAC permissions used (catalog defined in `../00-architecture-and-standards.md` §5.1):

| Action | Permission |
|---|---|
| Create/view/cancel special collections | `MANAGE_SPECIAL_COLLECTIONS` (write), `VIEW_TOWER_DATA` (read, incl. flat owners) |
| Mark a special collection due paid / view receipt | `RECORD_PAYMENT` (owned by Module 3, reused here — same permission gates maintenance and special-collection payment recording) |
| Record/edit/delete expenditures (incl. complex contribution) | `MANAGE_EXPENDITURE` (write), `VIEW_TOWER_DATA` (read) |

## Design decision: complex-level contribution modeled as a flagged Expenditure

**Choice:** one `expenditures` table with an `is_complex_contribution boolean NOT NULL DEFAULT false` flag plus two nullable columns (`complex_total_amount`, and `amount` doubles as the tower's own posted share for both regular and complex-contribution rows — no separate `tower_share_amount` column). Routing exposes both a generic `POST /expenditures` and a convenience `POST /expenditures/complex-contribution` that write to the *same table* through different Pydantic request schemas.

**Why not a separate `ComplexExpenditureContribution` table:** PRD §6.5.2 explicitly says the complex contribution "appears in the tower's expense books as a regular expenditure" and reports (category totals, collection-vs-expenditure summary) must include it uniformly. A separate table would force every report query to `UNION` two tables and would duplicate `tower_id`, `category`, `payment_mode`, `vendor/payee`, `attachment` — fields both entry types share. A single table with a flag keeps `SUM(amount)` correct everywhere with zero special-casing in report code (`WHERE is_complex_contribution` is only needed for the one screen that wants to filter/highlight these rows).

**Why not a separate `tower_share_amount` column (deviating from the suggested shape):** the "amount that posts to the tower's books" is the same concept for a regular expenditure and for a complex contribution — it should live in one column (`amount`) so every reporting/aggregate query reads a single field regardless of row type. Adding a second `tower_share_amount` column that is populated only when `is_complex_contribution=true` while a different `amount` column is used for the rest would create two amount semantics and an easy bug (a report forgetting to `COALESCE`). `complex_total_amount` is genuinely a different concept (reference-only, complex-wide, not postable) and is the only extra column needed.

**Why not two separate endpoints backed by different tables:** the dedicated `POST /expenditures/complex-contribution` path exists purely for frontend/UX clarity (a distinct form with distinct required fields: `complex_total_amount` optional, `amount` labeled "tower's share amount", `category` defaults to `other`) — it is a routing/schema convenience, not a separate resource. `GET /expenditures` and `GET /expenditures/{id}` are unified; `?is_complex_contribution=true` filters when needed.

## Reuse of Module 3 payment/receipt flow (concrete contract)

Module 3 owns and implements:

```
payments(
  id UUID PK,
  tower_id UUID NOT NULL,
  due_type VARCHAR NOT NULL,        -- 'maintenance' | 'special_collection' (discriminator, no cross-table DB FK)
  due_id UUID NOT NULL,             -- application-level FK resolved by due_type: maintenance_dues.id or special_collection_dues.id
  payment_date DATE NOT NULL,
  amount_received NUMERIC(12,2) NOT NULL,
  payment_mode VARCHAR NOT NULL,    -- 'cash' | 'bank_transfer' | 'cheque'
  reference_number VARCHAR NULL,
  recorded_by UUID NOT NULL,        -- association_members.id
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
-- unique partial index on (due_type, due_id) enforces "a due can only be paid once"

receipts(
  id UUID PK,
  payment_id UUID NOT NULL REFERENCES payments(id),
  due_type VARCHAR NOT NULL,        -- denormalized copy from payments, for query convenience
  receipt_number VARCHAR NOT NULL,  -- sequential PER TOWER, shared across due_type (one numbering sequence per tower, not one per due type)
  pdf_s3_key VARCHAR NOT NULL,
  generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (payment_id)
)
```

This module (4) does **not** create these tables. It depends on Module 3 exposing an internal service function with this signature. **This contract is now finalized in `../03-maintenance-billing/backend.md` §1.5/§1.6/§6.5** — the actual `payments`/`receipts` columns there additionally include `tower_id` and `due_id`/`due_type` on `receipts` too (denormalized for query convenience, matching what Module 5's reports need) and a `billing_period_label` column (holds `"Special Collection: {title}"` for this module's dues, `"{Month} {Year}"` for Module 3's) — treat that file as authoritative if it ever appears to drift from the illustrative shape below:

```python
async def record_payment(
    tower_id: UUID,
    due_type: Literal["maintenance", "special_collection"],
    due_id: UUID,
    payment_date: date,
    amount_received: Decimal,
    payment_mode: PaymentMode,
    reference_number: str | None,
    recorded_by: UUID,
) -> Receipt:
    """Validates due is not already paid, inserts Payment, transitions the due's
    status to 'paid' (dispatched by due_type to the correct due table),
    generates the receipt PDF (owner's name, tower name, flat number, amount,
    date, mode, ref, next sequential receipt_number for the tower), uploads it
    to S3 under receipts/{tower_id}/{receipt_id}.pdf, and returns the Receipt."""
```

Module 4's `POST .../special-collections/{id}/dues/{due_id}/mark-paid` handler is a thin wrapper: validate the due belongs to `special_collection_id`/`tower_id`, call `record_payment(due_type="special_collection", due_id=due.id, ...)`, transition `special_collection_dues.status` to `paid` (this may happen inside `record_payment` itself if Module 3 owns due-status transitions generically via `due_type` dispatch — **this module's router does not implement its own status-transition or receipt-generation logic**, only the HTTP boundary and its own permission check). The receipt's "billing period" label field is populated with `"Special Collection: {special_collection.title}"` instead of a maintenance billing-cycle label — this is the one piece of due-type-specific formatting the receipt template needs (a single conditional on `due_type`), owned by Module 3's template code.

If Module 3 ultimately ships a different concrete shape than the one above, the owning developers must reconcile before either module ships — the discriminator contract (`due_type` + `due_id`, single `payments`/`receipts` tables, one receipt-number sequence per tower) is the agreed integration point and should not silently drift.

## Data model (this module's own tables)

```
special_collections(
  id UUID PK,
  tower_id UUID NOT NULL,
  title VARCHAR NOT NULL,
  description TEXT NULL,
  total_amount NUMERIC(12,2) NOT NULL CHECK (total_amount > 0),
  split_basis VARCHAR NOT NULL DEFAULT 'equal' CHECK (split_basis = 'equal'),  -- enum widened post-v1.0
  due_date DATE NOT NULL,
  dues_generated_at TIMESTAMPTZ NULL,   -- set the moment dues are created; NULL only during the brief async-job window
  skipped_flats JSONB NULL,             -- [{flat_id, flat_number, reason}] snapshot from generation, for admin visibility
  created_by UUID NOT NULL,             -- association_members.id
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  deactivated_at TIMESTAMPTZ NULL       -- soft-delete/cancel; only allowed pre-generation or if zero dues paid (see below)
)

special_collection_dues(
  id UUID PK,
  special_collection_id UUID NOT NULL REFERENCES special_collections(id),
  tower_id UUID NOT NULL,               -- denormalized for direct tower-scoped queries/index
  flat_id UUID NOT NULL,                -- Module 2 Flat
  owner_id UUID NOT NULL,               -- Module 2 Owner — the PRIMARY owner snapshotted at generation time; never a tenant
  amount NUMERIC(12,2) NOT NULL,
  due_date DATE NOT NULL,               -- copied from parent at generation time (mirrors billing-cycle due immutability)
  status VARCHAR NOT NULL DEFAULT 'pending',  -- 'pending' | 'paid' | 'overdue'
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (special_collection_id, flat_id)
)

expenditures(
  id UUID PK,
  tower_id UUID NOT NULL,
  expenditure_date DATE NOT NULL,
  category VARCHAR NOT NULL,            -- enum: 'cleaning' | 'security' | 'repairs' | 'utilities' | 'other'
  description TEXT NOT NULL,
  vendor_payee_name VARCHAR NOT NULL,
  amount NUMERIC(12,2) NOT NULL CHECK (amount > 0),   -- the amount that posts to THIS tower's books (= tower's share when is_complex_contribution)
  payment_mode VARCHAR NOT NULL,        -- 'cash' | 'bank_transfer' | 'cheque'
  attachment_s3_key VARCHAR NULL,
  is_complex_contribution BOOLEAN NOT NULL DEFAULT false,
  complex_total_amount NUMERIC(12,2) NULL,  -- reference only; NULL unless is_complex_contribution; NEVER summed in reports
  recorded_by UUID NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  deactivated_at TIMESTAMPTZ NULL,       -- soft-delete, per ../00-architecture-and-standards.md §6
  CHECK (complex_total_amount IS NULL OR is_complex_contribution)
)
```

Grace period application: `special_collection_dues.status` transitions `pending -> overdue` via the same scheduled job/mechanism Module 3 builds for maintenance dues (tower's configured grace period, PRD §6.4 "the grace period configured for the tower applies to special collection dues as well") — reuse that job, do not build a second overdue-transition scheduler. It should iterate both `maintenance_dues` and `special_collection_dues` (or run once per due-type table with shared logic) keyed off each tower's grace-period config (Module 3-owned).

## Endpoints

### Special Collections

**`POST /api/v1/towers/{tower_id}/special-collections`** — create + auto-generate dues (`MANAGE_SPECIAL_COLLECTIONS`)
```json
// Request
{ "title": "Lift Modernization Fund", "description": "string|null", "total_amount": 250000.00, "split_basis": "equal", "due_date": "2026-09-01" }
```
- ≤300 active flats: synchronous, returns `201` with the created collection + `dues_generated: true` (budget: 3s p95, per `../00-architecture-and-standards.md` §4).
- \>300 active flats: enqueues an SQS job (`special-collection-jobs`, see `cloud.md`), returns `202 { "job_id": "...", "dues_generated": false }`; client polls `GET /api/v1/towers/{tower_id}/jobs/{job_id}`.
- Response body always includes `skipped_flats: [{flat_id, flat_number, reason: "NO_ACTIVE_OWNER"}]` (empty array if none).
- Equal-split calculation: `total_paise = round(total_amount * 100)`; `n = count(active flats with >=1 active owner)`; `base_paise = total_paise // n`; `remainder = total_paise % n`; sort eligible flats by `flat_number` ascending; the first `remainder` flats get `base_paise + 1`, the rest get `base_paise`; each due's `amount = paise / 100`. This guarantees `sum(due.amount) == total_amount` exactly, with deterministic, reproducible distribution of odd cents.

**`GET /api/v1/towers/{tower_id}/special-collections`** — paginated list (`VIEW_TOWER_DATA`), envelope per §6; filters: `status=open|closed` (derived: `open` = at least one due not `paid`), `?page=&page_size=`.

**`GET /api/v1/towers/{tower_id}/special-collections/{id}`** — detail (`VIEW_TOWER_DATA`), includes rollup: `total_amount`, `collected_amount`, `pending_count`, `paid_count`, `overdue_count`, `skipped_flats`.

**`DELETE /api/v1/towers/{tower_id}/special-collections/{id}`** — cancel/soft-delete (`MANAGE_SPECIAL_COLLECTIONS`). Allowed only if zero dues have status `paid`; otherwise `409 { "error_code": "IMMUTABLE_RECORD", "message": "Cannot cancel a special collection with recorded payments." }`. No `PUT`/`PATCH` — a special collection is immutable once dues exist (mirrors billing-cycle immutability, §6), matching the fact that dues are always generated at creation time in this module (no draft state).

### Special Collection Dues

**`GET /api/v1/towers/{tower_id}/special-collections/{id}/dues`** — paginated list (`VIEW_TOWER_DATA`; flat owners see only their own flat's due via the standard scoping applied at the query layer). Filters: `status`, `flat_id`, `owner_id`.

**`GET /api/v1/towers/{tower_id}/special-collections/{id}/dues/{due_id}`** — detail.

**`POST /api/v1/towers/{tower_id}/special-collections/{id}/dues/{due_id}/mark-paid`** — (`RECORD_PAYMENT`)
```json
{ "payment_date": "2026-07-15", "amount_received": 1000.00, "payment_mode": "bank_transfer", "reference_number": "UTR123456|null" }
```
Delegates to Module 3's `record_payment(due_type="special_collection", ...)` as described above. `409 { "error_code": "DUE_ALREADY_PAID" }` if already paid.

**`GET /api/v1/towers/{tower_id}/special-collections/{id}/dues/{due_id}/receipt`** — returns a pre-signed S3 GET URL for the receipt PDF (delegates to Module 3's storage; this module only proxies the request after checking tower/collection scoping).

### Expenditures

**`POST /api/v1/towers/{tower_id}/expenditures`** — (`MANAGE_EXPENDITURE`)
```json
{ "expenditure_date": "2026-07-05", "category": "repairs", "description": "Elevator motor replacement", "vendor_payee_name": "ABC Elevators Pvt Ltd", "amount": 45000.00, "payment_mode": "bank_transfer", "attachment_s3_key": "expenditure-attachments/.../invoice.pdf|null" }
```

**`POST /api/v1/towers/{tower_id}/expenditures/complex-contribution`** — (`MANAGE_EXPENDITURE`), dedicated schema, writes to the same `expenditures` table with `is_complex_contribution=true`:
```json
{ "expenditure_date": "2026-07-05", "description": "Complex-wide painting", "vendor_payee_name": "XYZ Painters", "complex_total_amount": 500000.00, "amount": 80000.00, "payment_mode": "cheque", "category": "other", "attachment_s3_key": "...|null" }
```
`amount` here is labeled "tower's share amount" in the schema docstring/OpenAPI description to avoid ambiguity; `category` defaults to `"other"` if omitted.

**`GET /api/v1/towers/{tower_id}/expenditures`** — paginated list (`VIEW_TOWER_DATA`); filters: `category`, `is_complex_contribution`, `date_from`, `date_to`.

**`GET /api/v1/towers/{tower_id}/expenditures/{id}`** — detail.

**`PUT /api/v1/towers/{tower_id}/expenditures/{id}`** — edit (`MANAGE_EXPENDITURE`); full audit log entry (before/after) per §6; expenditures are not on the immutable-record list in the PRD (unlike billing cycles/paid dues), so edits are permitted but always audited.

**`DELETE /api/v1/towers/{tower_id}/expenditures/{id}`** — soft-delete (`deactivated_at`), audited.

**`POST /api/v1/towers/{tower_id}/expenditures/attachment-upload-url`** — (`MANAGE_EXPENDITURE`) returns a pre-signed S3 PUT URL + the `attachment_s3_key` the client must submit back in the create/edit call. Server validates `content_type` (PDF/JPEG/PNG only) and enforces a `Content-Length` ceiling of 10 MB on the presigned policy — see `cloud.md`.

**`GET /api/v1/towers/{tower_id}/expenditures/{id}/attachment`** — pre-signed GET URL for the stored attachment (`VIEW_TOWER_DATA` — flat owners can view attachments since expenditures are read-only-visible to them per PRD §6.5.1).

## Pydantic schemas (representative)

```python
class SplitBasis(str, Enum):
    equal = "equal"

class SpecialCollectionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    total_amount: Decimal = Field(gt=0, decimal_places=2)
    split_basis: SplitBasis = SplitBasis.equal
    due_date: date

class SkippedFlat(BaseModel):
    flat_id: UUID
    flat_number: str
    reason: Literal["NO_ACTIVE_OWNER"]

class SpecialCollectionOut(BaseModel):
    id: UUID
    tower_id: UUID
    title: str
    description: str | None
    total_amount: Decimal
    split_basis: SplitBasis
    due_date: date
    dues_generated_at: datetime | None
    skipped_flats: list[SkippedFlat]
    collected_amount: Decimal
    pending_count: int
    paid_count: int
    overdue_count: int
    created_at: datetime

class SpecialCollectionDueOut(BaseModel):
    id: UUID
    special_collection_id: UUID
    flat_id: UUID
    flat_number: str        # joined from Module 2 Flat for display
    owner_id: UUID
    owner_name: str          # joined from Module 2 Owner
    amount: Decimal
    due_date: date
    status: Literal["pending", "paid", "overdue"]

class MarkPaidRequest(BaseModel):
    payment_date: date
    amount_received: Decimal = Field(gt=0, decimal_places=2)
    payment_mode: Literal["cash", "bank_transfer", "cheque"]
    reference_number: str | None = None

class ExpenditureCategory(str, Enum):
    cleaning = "cleaning"
    security = "security"
    repairs = "repairs"
    utilities = "utilities"
    other = "other"

class ExpenditureCreate(BaseModel):
    expenditure_date: date
    category: ExpenditureCategory
    description: str = Field(min_length=1)
    vendor_payee_name: str = Field(min_length=1)
    amount: Decimal = Field(gt=0, decimal_places=2)
    payment_mode: Literal["cash", "bank_transfer", "cheque"]
    attachment_s3_key: str | None = None

class ComplexContributionCreate(BaseModel):
    expenditure_date: date
    description: str = Field(min_length=1)
    vendor_payee_name: str = Field(min_length=1)
    complex_total_amount: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    amount: Decimal = Field(gt=0, decimal_places=2, description="Tower's own share amount — the only figure posted to this tower's books.")
    payment_mode: Literal["cash", "bank_transfer", "cheque"]
    category: ExpenditureCategory = ExpenditureCategory.other
    attachment_s3_key: str | None = None
```

## Backend Test Plan

**Integration tests:**

1. **Due generation always targets the owner, never the tenant.** Given a flat that is tenant-occupied (active `Tenant` record present), creating a special collection produces a `special_collection_dues` row whose `owner_id` is the flat's primary owner — assert `owner_id != tenant.id`-equivalent check (owner_id must resolve to an `Owner`, and the test fixture's tenant must not appear anywhere on the due).
2. **Equal-split calculation with correct rounding.** `total_amount=100000.00` across `N=7` active flats: assert `sum(due.amount for due in dues) == 100000.00` exactly; assert exactly `100000*100 % 7` flats received one extra paisa; assert those flats are the first N (by `flat_number` ascending) among eligible flats — deterministic on repeated runs with the same input.
3. **Flat with no active owner is skipped, not fatal.** Fixture: 10 active flats, one has all owners soft-deleted (no active `FlatOwnership`). Creating a special collection generates 9 dues, the response's `skipped_flats` contains the 10th flat with `reason=NO_ACTIVE_OWNER`, and the request still returns `201` (not a 4xx/5xx).
4. **Multiple simultaneous open special collections.** Create special collection A, do not mark any due paid, then create special collection B on the same tower — assert `201` for B, both collections' `GET .../dues` return independent, non-overlapping due sets.
5. **Special collection is immutable after creation.** Assert there is no `PUT`/`PATCH` route registered for `/special-collections/{id}`; assert `DELETE` returns `409 IMMUTABLE_RECORD` once at least one due on that collection has `status='paid'`.
6. **Mark-paid delegates correctly and cannot double-pay.** Marking a due paid calls Module 3's `record_payment` with `due_type='special_collection'`; asserts a `Receipt` row exists referencing that payment, the due's status is `paid`, and a second `mark-paid` call on the same due returns `409 DUE_ALREADY_PAID`.
7. **Receipt is issued in the owner's name even when a tenant exists.** For a tenant-occupied flat, after marking its special collection due paid, assert the generated receipt's owner-name field matches the flat's primary owner, not the tenant.
8. **Grace period / overdue transition applies to special collection dues.** A due with `due_date` + tower's configured grace period elapsed and no payment recorded transitions to `overdue` via the shared scheduled job (same mechanism Module 3 uses for maintenance dues).
9. **Expenditure with attachment stores S3 key and resolves a pre-signed GET URL.** `POST .../expenditures/attachment-upload-url` returns a key under `expenditure-attachments/{tower_id}/{expenditure_id}/{filename}`; after `PUT`-ing a file to the presigned URL and creating the expenditure referencing that key, `GET .../expenditures/{id}/attachment` returns a resolvable pre-signed GET URL (mocked S3 in CI, e.g. via `moto`).
10. **Expenditure without attachment is valid.** `POST .../expenditures` with `attachment_s3_key` omitted succeeds and stores `NULL`.
11. **Oversized attachment is rejected before reaching storage.** Attempting to use `attachment-upload-url` with a declared `content_length` over 10 MB (or a subsequent PUT exceeding the presigned policy's max) fails with a 4xx and no `Expenditure` row or S3 object is created.
12. **Complex-contribution expenditure appears in regular list and report totals correctly.** Create a complex-contribution expenditure with `complex_total_amount=500000.00, amount=80000.00`; assert it appears in `GET .../expenditures` (unfiltered) and in the tower's expenditure/category report with only `80000.00` counted — `complex_total_amount` must not appear in any `SUM()`-derived report field.
13. **Async threshold for bulk due generation.** With a fixture of >300 active flats, `POST .../special-collections` returns `202` with a `job_id`, and polling `GET /api/v1/towers/{tower_id}/jobs/{job_id}` eventually reflects `done` with the dues fully generated (same pattern/tests as Module 3's billing-cycle async path — do not re-derive a different job contract).

**What must NOT break:**

- Module 2's `Flat`/`Owner`/`Tenant` read paths — this module only reads, never writes those tables.
- Module 3's maintenance due generation, payment recording, and receipt numbering sequence — special collection payments share the same receipt-number sequence per tower; a bug here must not cause duplicate or skipped maintenance receipt numbers.
- Existing audit log entries for other modules — this module adds new `audit_log` rows (expenditure edits, special collection creation/cancellation) but never mutates existing entries.
- RBAC permission checks — `MANAGE_SPECIAL_COLLECTIONS` and `MANAGE_EXPENDITURE` must be independently revocable without affecting `RECORD_PAYMENT`-gated actions (mark-paid) or vice versa.
- Report totals owned by Module 5 — the `is_complex_contribution`/`complex_total_amount` distinction must remain query-filterable so Module 5's expenditure report can do category-wise totals without double-counting.
