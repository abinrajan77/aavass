# Spec: Module 4 — Special Collections & Expenditure Management

> One page in spirit; split across 4 files per repo convention (`overview.md`, `backend.md`, `frontend.md`, `cloud.md`).
> Read `../00-architecture-and-standards.md` and `../06-cloud-devops.md` first — this spec reuses their conventions rather than redefining them.

## Problem

Tower associations have no structured way to levy one-off charges for unexpected large expenses (e.g. lift repair, painting) outside the monthly maintenance cycle, and no auditable place to record how common funds and the tower's share of complex-wide costs are spent. Today this happens over spreadsheets or messaging apps, with no guarantee the levy is billed fairly to every flat, no guarantee it lands on the owner (not a tenant who may leave), and no attachment trail for bills/invoices.

## Scope & ownership

Owns: `SpecialCollection`, `SpecialCollectionDue`, `Expenditure` (including complex-level contribution entries — modeled as a flagged `Expenditure`, not a separate entity; see `backend.md`).

Reads (does not own, does not duplicate): `Flat`, `Owner`, `FlatOwnership` (Module 2); `AssociationMember`/RBAC (Module 1).

Reuses (does not redesign): Module 3's `Payment`/`Receipt` subsystem for special collection due payments and receipts — see the "Cross-module dependency" note below and `backend.md` §"Reuse of Module 3 payment/receipt flow" for the concrete contract.

## Non-goals (v1.0)

Per PRD §3.2 and §6.4–6.5:

- **No split basis other than equal-split.** `SpecialCollection.split_basis` is modeled as an enum for future extensibility but only `equal` is a legal value in v1.0. Per-flat weighting (by carpet area, by co-owner share, etc.) is out of scope.
- **No cross-tower reconciliation for complex-level expenses.** A `ComplexExpenditureContribution` entry records only this tower's share and, optionally, the complex-wide total for reference. There is no ledger that reconciles what other towers recorded, no complex-level admin role, and no complex-level financial rollup (PRD §3.2, §6.5.2, §10 — "no complex-level administrator role in v1.0").
- **No online payment gateway.** Special collection dues are recorded as paid manually by the admin/treasurer, exactly like maintenance dues (PRD §3.2).
- **No per-flat special collection overrides.** The equal-split formula applies uniformly to every currently-active flat; there is no mechanism to exempt or discount an individual flat within a collection.
- **No automated notifications.** This module prepares no notification text itself — that is Module 5's concern, consuming due/payment status this module produces (per `00-architecture-and-standards.md` §7).
- **No expenditure approval workflow.** Recording an expenditure is a single admin action; there is no multi-step approval/sign-off chain in v1.0.

## Cross-module dependency: Module 3's payment/receipt flow

Special collection dues are paid, tracked, and receipted through **the same subsystem Module 3 builds for maintenance dues** — this module does not define its own payment or receipt tables. Concretely (detailed in `backend.md`):

- Module 3 owns `payments` and `receipts` tables keyed by a `due_type` discriminator (`'maintenance' | 'special_collection'`) plus a polymorphic `due_id`.
- This module's "mark special collection due paid" endpoint lives under this module's router (tower/special-collection scoped, for URL locality) but internally calls Module 3's shared payment-recording service function, passing `due_type='special_collection'`.
- Receipt PDF generation, sequential receipt numbering, and S3 storage are 100% Module 3's implementation — this module only supplies the label ("Special Collection: {title}" instead of a billing period) and the owner/flat/amount data.

**This is a hard dependency**: this module cannot be fully implemented (payment/receipt endpoints) until Module 3's `payments`/`receipts` tables and service exist with the `due_type` discriminator. Due generation, listing, and expenditure recording have no such dependency and can be built first.

## Edge cases

- **Special collection created while a flat is vacant or has no owner on record.** Vacant occupancy status is irrelevant to special collections (they always bill the owner, never the tenant/resident) — a vacant flat still gets a due as long as it has at least one active owner. But if a flat has **zero** active owners on record (a data-quality gap — e.g. an owner was deactivated and no replacement added), that flat cannot receive a due. The system must **skip** that flat, continue generating dues for every other active flat, and surface the skipped flat(s) in the creation response (`skipped_flats: [{flat_id, flat_number, reason: "NO_ACTIVE_OWNER"}]`) so the admin can fix the data and the collection is not silently incomplete.
- **Multiple simultaneous open special collections on the same tower.** Explicitly allowed by PRD §6.4 ("Multiple special collections can be open simultaneously"). Each collection and its dues are fully independent — no merging, no shared due records, no limit on concurrent open collections.
- **Expenditure with no attachment vs. one exceeding the file-size limit.** Attachment is optional (`attachment_s3_key` nullable) — an expenditure with no bill/invoice on hand is a normal, valid record. A file that exceeds the configured limit (10 MB, matching the receipt/attachment pattern in `06-cloud-devops.md`) must be rejected **before** it reaches S3, with a clear field-level validation error, both client-side (zod) and server-side (the pre-signed upload flow enforces a `Content-Length` policy on the PUT URL).
- **Complex-level expenditure: total vs. tower's share.** `complex_total_amount` is optional and reference-only (helps the admin/owners see proportionality) — it is **never** summed into the tower's own expenditure totals, category-wise report totals, or collection-vs-expenditure summary. Only `amount` (the tower's own posted share) is a first-class ledger figure. This must hold in both the API response shape and every report/aggregate query.

## Acceptance criteria

1. **GIVEN** a tower with 250 currently-active flats, **WHEN** an admin creates a special collection with `total_amount = 250000.00` and `split_basis = equal`, **THEN** the system generates exactly 250 dues synchronously (within the 3s sync budget), each due's `owner_id` is the flat's current primary owner — including for tenant-occupied flats, where the due still goes to the owner, never the tenant.
2. **GIVEN** a tower already has one open special collection with unpaid dues, **WHEN** the admin creates a second special collection on the same tower, **THEN** creation succeeds and both collections' dues are tracked independently (no error, no merge).
3. **GIVEN** a `SpecialCollectionDue` in `pending` or `overdue` status, **WHEN** the admin marks it paid with payment date/mode/amount, **THEN** the request is delegated to Module 3's shared payment service (`due_type='special_collection'`), a receipt PDF is generated and stored via Module 3's flow, the receipt is issued in the flat owner's name (never the tenant's), and the due transitions to `paid`.
4. **GIVEN** a flat with zero active owners at due-generation time, **WHEN** a special collection is created, **THEN** that flat is skipped (no due created for it), every other active flat still receives a due, and the skipped flat appears in the creation response with reason `NO_ACTIVE_OWNER`.
5. **GIVEN** an admin recording a tower expenditure with category, vendor, amount, and no attachment, **WHEN** the record is submitted, **THEN** it saves successfully with `attachment_s3_key = null` and appears in the expenditure list/reports.
6. **GIVEN** an admin recording a complex-level expenditure with `complex_total_amount = 500000.00` and `tower_share_amount (amount) = 80000.00`, **WHEN** the record is submitted, **THEN** it appears in the tower's regular expenditure list, only `80000.00` is included in category totals and the collection-vs-expenditure summary, and `complex_total_amount` is displayed only as read-only reference context.
7. **GIVEN** an expenditure attachment file over the 10 MB limit, **WHEN** the admin attempts to attach it, **THEN** the upload is rejected before reaching S3 with a field-level error, and no `Expenditure` or partial S3 object is created.
