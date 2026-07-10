# Module 3 — Maintenance Billing — Overview

> Reads shared conventions from `../00-architecture-and-standards.md` (design system, latency budgets, RBAC, API conventions) and `../06-cloud-devops.md` (SQS, S3). Do not duplicate those decisions here — this file covers only what is specific to maintenance billing.

## Problem

Tower admins currently have no structured way to calculate monthly maintenance dues from a formula, enforce a fair grace period before flagging non-payment, or produce a receipt in the correct owner's name when a tenant is the one who actually pays. This module is the financial engine that turns a configured formula + billing cycle into per-flat dues, tracks their payment status, and generates immutable, auditable receipts.

## Non-goals (v1.0)

Pulled directly from PRD §3.2 and §10 — this module deliberately does **not**:

- Support **per-flat maintenance formula overrides**. The formula (base amount + per-sq-ft rate) applies uniformly to every flat in the tower; there is no flat-level exception mechanism (PRD §6.3.1, §10).
- Integrate an **online payment gateway**. All payments are recorded manually by the admin/treasurer after money has already changed hands through some external channel (PRD §3.2, §10).
- Send **automated notifications** (SMS/WhatsApp) when a due is generated, becomes overdue, or is paid. v1.0 only prepares message text for the admin to copy/paste manually (owned by Module 5); this module exposes the underlying due/payment events but does not dispatch anything (PRD §8.1).
- Handle **special collections**. Special collection dues follow a structurally similar but separately-owned workflow in Module 4 (always assigned to the owner, never the tenant) — do not fold that logic in here.
- Support **partial payments** or payment plans. A due is either fully unpaid (Pending/Overdue) or fully paid in one recorded transaction (PRD gives no split-payment mechanism).
- Perform **cross-tower or complex-level financial consolidation**. Every calculation is scoped to one tower.

## Edge cases

1. **Mid-cycle tenant change does not alter an already-generated due.** `maintenance_dues.assigned_to_*` is a snapshot captured at billing-cycle generation time. If the tenant vacates or a new tenant moves in after the due exists, that due keeps its original assignee. Per PRD §6.2.3, it is the flat owner's responsibility to make sure payment reaches the association — directly or via the outgoing/incoming tenant — and the admin simply records payment and issues the receipt when it arrives, without re-pointing the due.
2. **Grace period of 0 means Overdue the day after the due date.** `due_date + 0` has already passed as soon as `due_date` ends, so the status flips on `due_date + 1`. This must hold as a boundary condition, not an approximation (PRD §6.3.2).
3. **Billing cycles are immutable once dues exist; formula/grace-period changes never retroact.** Both `MaintenanceFormula` and the grace-period config are versioned with an `effective_from` date. A `BillingCycle` snapshots the formula version and grace-period value in effect at the moment dues are generated. Editing the formula or grace period afterward only affects future cycles — it cannot change historical dues or their overdue timing (PRD §6.3.1, §6.3.2).
4. **A co-owned flat's receipt always names the primary owner, never all co-owners or the tenant.** Even though PRD §6.3.5 lists "owner name(s)" as a receipt field, PRD §10 resolves the ambiguity: "In co-ownership, the primary owner is the named recipient on receipts." The receipt's addressee is always the single flat owner flagged `is_primary_contact = true` on the flat (owned by Module 2), regardless of who paid.
5. **A due assigned to a tenant whose lease ends before the due is paid.** Because the due's `assigned_to` is a frozen snapshot (edge case 1), the admin does not chase the vacated tenant through the system. The dues list/detail view must surface the flat's primary owner as the practical follow-up contact alongside the (now-stale) tenant assignee, since PRD makes the owner ultimately responsible for ensuring payment reaches the association.
6. **Formula with both components at zero (base = 0, rate = 0).** Technically valid per the scenario table in PRD §6.3.1 (each component is independently zeroable) — the system must allow saving and generating a cycle where every due amount is ₹0; it is not an input error, though the frontend should flag it as unusual before submit (see `frontend.md`).
7. **Duplicate billing-cycle generation for the same tower + month + year is rejected**, not silently merged or duplicated — this is the idempotency key referenced in `06-cloud-devops.md` §4 and enforced by a DB unique constraint plus a `409` error.
8. **Marking an already-Paid due as Paid again is rejected** (`409 DUE_ALREADY_PAID`) — a due can have at most one `payments` row.
9. **Bulk cycle generation beyond ~300 flats runs asynchronously** (per `00-architecture-and-standards.md` §4); the dues list for that cycle is incomplete/absent until the job finishes, and the frontend must reflect a "generating" state rather than an empty list.
10. **A flat deactivated (soft-deleted in Module 2) after its due was generated** keeps that historical due untouched; only flats active at generation time receive a due for a *new* cycle.
11. **Vacant flats** (no active tenant, `occupancy_status = Vacant`) fall into the "otherwise" branch of the assignment rule — due goes to the primary owner, same as Owner-occupied.
12. **No owner flagged as primary contact on a flat** (a Module 2 data-integrity gap). Cycle generation must not silently guess — it should fail generation for that specific flat with a clear error (surfaced per-flat, not aborting the whole cycle) rather than defaulting to an arbitrary co-owner, since receipts must be legally attributable.
13. **Rounding**: all amounts are INR with 2 decimal places; `Carpet Area × Per Sq Ft Rate` is rounded half-up to the nearest paisa before adding the base amount.
14. **Formula/grace-period `effective_from` in the future**: cycle generation always uses the version whose `effective_from` is the latest one `<=` the cycle's creation date (not the due date, not the billing month).

## Acceptance criteria

1. **GIVEN** a formula with base=2000, rate=0 **WHEN** computing a due for a flat with carpet_area=850 **THEN** the due amount is exactly ₹2000.00.
2. **GIVEN** a formula with base=0, rate=2 **WHEN** computing a due for carpet_area=850 **THEN** the due amount is exactly ₹1700.00.
3. **GIVEN** a formula with base=1000, rate=1.5 **WHEN** computing a due for carpet_area=600 **THEN** the due amount is exactly ₹1900.00.
4. **GIVEN** a tower with 250 active flats **WHEN** admin submits `POST /billing-cycles` for a new month/year **THEN** the cycle and all 250 dues are created synchronously within the 5s budget and the response is `201` with the full cycle summary.
5. **GIVEN** a tower with 450 active flats **WHEN** admin submits `POST /billing-cycles` **THEN** the API returns `202 Accepted` with a `job_id` immediately, and dues appear only once the async job (SQS `billing-cycle-jobs`) completes.
6. **GIVEN** a flat is Tenant-occupied with an active tenant **WHEN** a billing cycle is generated **THEN** that flat's due is assigned to the active tenant (`assigned_to_type = 'tenant'`).
7. **GIVEN** a flat is Owner-occupied or Vacant **WHEN** a billing cycle is generated **THEN** that flat's due is assigned to the flat's primary owner (`assigned_to_type = 'owner'`).
8. **GIVEN** a due with `due_date = 2026-07-10` and `grace_period_days = 5` **WHEN** the current date is `2026-07-15` **THEN** the due's status remains `Pending`; **WHEN** the current date becomes `2026-07-16` **THEN** the status is `Overdue`.
9. **GIVEN** a due with `grace_period_days = 0` and `due_date = 2026-07-10` **WHEN** the current date is `2026-07-11` **THEN** the status is `Overdue`.
10. **GIVEN** a Pending due **WHEN** admin calls `PATCH /dues/{due_id}/mark-paid` with a valid payload **THEN** the due's status becomes `Paid`, a `payments` row is created, a PDF receipt is generated and stored in S3, and the response includes a `receipt_id`/download link — all within the 2s p95 receipt budget.
11. **GIVEN** a due that is already `Paid` **WHEN** admin calls `mark-paid` again **THEN** the API returns `409 DUE_ALREADY_PAID` and no duplicate payment/receipt is created.
12. **GIVEN** a flat with a tenant as the due's assigned payer **WHEN** the receipt is generated **THEN** the receipt PDF names the flat's primary owner, not the tenant.
13. **GIVEN** a billing cycle that already has dues recorded **WHEN** any client attempts `PUT`/`DELETE` on that cycle **THEN** the API returns `409 IMMUTABLE_RECORD`.
14. **GIVEN** the admin changes the maintenance formula or grace period today **WHEN** viewing a billing cycle generated last month **THEN** that cycle's dues/overdue timing are computed from the formula/grace-period version in effect at the time that cycle was generated, not the new values.
15. **GIVEN** a tenant's lease ends and they vacate mid-cycle **WHEN** viewing the existing due for that cycle **THEN** `assigned_to` still shows the (now former) tenant and the due amount/status are unaffected.
