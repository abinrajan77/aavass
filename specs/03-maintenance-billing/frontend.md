# Module 3 — Maintenance Billing — Frontend

> Uses the shared "Tower" design system from `../00-architecture-and-standards.md` §3 (shadcn/ui + magicui, status color tokens: Paid = `success`, Pending = `warning`, Overdue = `destructive`). All financial forms use `react-hook-form` + `zod`, mirroring the backend Pydantic constraints in `backend.md` §7.

## 1. Routes

| Route | Purpose | Guard |
|---|---|---|
| `/towers/[towerId]/billing/formula` | Configure maintenance formula (base amount + per-sq-ft rate) with live preview; view version history | `CONFIGURE_BILLING` to edit, `VIEW_TOWER_DATA` to view |
| `/towers/[towerId]/billing/grace-period` | Configure grace period (days); shown as a `Tabs` sibling of the formula page (`Tabs`: "Formula" / "Grace Period") | `CONFIGURE_BILLING` to edit |
| `/towers/[towerId]/billing/cycles` | List all billing cycles for the tower; "Generate Cycle" action | `CREATE_BILLING_CYCLE` to generate, `VIEW_TOWER_DATA` to view |
| `/towers/[towerId]/billing/cycles/[cycleId]` | Cycle detail: stat cards + dues `DataTable` with status tabs, mark-paid, receipt download | `RECORD_PAYMENT` to mark paid, `VIEW_TOWER_DATA` to view |
| `/towers/[towerId]/billing/dues` | Cross-cycle "at a glance" pending/overdue dues list (dashboard drill-down, PRD §6.3.4) | `VIEW_TOWER_DATA` |

## 2. Screen-by-screen components

### 2.1 `/billing/formula`
- `Form` (react-hook-form + zod resolver): `base_amount` (number input), `per_sqft_rate` (number input), `effective_from` (`Calendar` + `Popover` date picker, defaults to today, cannot be in the past).
- **Live-calculated preview**: as the admin types, a read-only card computes `Monthly Maintenance = base_amount + carpet_area × per_sqft_rate` for 2-3 representative carpet areas (e.g. 600, 900, 1200 sq.ft. — either hardcoded sample sizes or the tower's actual min/median/max carpet area pulled from Module 2's flat list) so the admin can sanity-check the formula before saving. Recomputed client-side on every keystroke — no API round-trip needed for the preview itself.
- Version history: `Table` below the form showing past formula versions (`base_amount`, `per_sqft_rate`, `effective_from`, changed-by), read-only, newest first — makes the "formula changes are versioned" rule visible rather than a hidden implementation detail.
- `Sonner` toast on save success/failure.

### 2.2 `/billing/grace-period`
- `Form`: single `grace_period_days` number input (`Select` or plain number field, min 0). Inline helper text: "0 days means a due becomes Overdue the day after its due date." (directly surfaces PRD §6.3.2's rule so admins don't set 0 by accident.)
- Version history `Table` (same pattern as formula).

### 2.3 `/billing/cycles`
- `DataTable`: columns = Month/Year, Due Date, Status (`Badge`: `generating` = muted/outline, `active` = default), Total Dues, Total Collected, Pending Count, Overdue Count.
- "Generate Cycle" button opens a `Dialog` with `Form`: `month` (`Select` 1-12), `year` (number input), `due_date` (`Calendar` + `Popover`).
  - On submit: if the API returns `201`, close dialog, toast success, row appears immediately.
  - If the API returns `202` (async path, >300 flats), dialog shows a progress state ("Generating dues for 450 flats — this may take a minute") and polls the shared canonical job route `GET /api/v1/towers/{tower_id}/jobs/{job_id}` every 2s; on `done`, refreshes the cycle row; the cycles list shows that row's status as `generating` (with a `Skeleton`/spinner badge) until then.
  - `409 BILLING_CYCLE_ALREADY_EXISTS` → inline form error under the month/year fields, not a toast (it's a correctable input error, not a background failure).

### 2.4 `/billing/cycles/[cycleId]`
- Header: cycle month/year, due date, formula snapshot used ("Base ₹X + ₹Y/sq.ft., effective from …") and grace period snapshot used — both read-only, reinforcing that this cycle is frozen to whatever was in effect at generation time.
- Stat cards (magicui `NumberTicker`, laid out in a `BentoGrid` row): **Total Collected This Cycle**, **Pending Count**, **Overdue Amount**. Data from `GET /billing-dashboard-stats` scoped to this cycle. Build this as a standalone, exported component (`components/billing/BillingStatCards.tsx`) taking `{ totalCollected, pendingCount, overdueAmount }` as props — Module 5's admin dashboard reuses this exact component for the tower-wide (cross-cycle) equivalent, so keep it free of cycle-specific data-fetching logic (fetch happens in the parent page, component only renders).
- Dues `DataTable` with `Tabs`: All / Pending / Paid / Overdue (maps to `?status=` query param). Columns: Flat Number, Assigned To (name + `tenant`/`owner` tag), Amount, Due Date, Status `Badge` (using the exact `success`/`warning`/`destructive` tokens — never ad-hoc colors, per `00-architecture-and-standards.md` §3.1), row actions.
- Row action "Mark Paid" (only enabled for Pending/Overdue rows, gated by `RECORD_PAYMENT` permission via `<Can permission="RECORD_PAYMENT">`) opens a `Dialog` with a `Form`:
  - `payment_date` (`Calendar` + `Popover`, cannot be in the future)
  - `amount_received` (number input, must be `> 0`)
  - `payment_mode` (`Select`: Cash / Bank Transfer / Cheque)
  - `reference_number` (optional text input, shown/relevant mainly for bank transfer/cheque but not hard-gated by mode in v1.0)
  - On submit success: dialog closes, the row's `Badge` updates to `success`/"Paid" immediately (optimistic or refetch-on-success via TanStack Query invalidation), and a "Download Receipt" action appears on that row.
  - On `409 DUE_ALREADY_PAID` (e.g. double-click race): toast error, dialog closes, row already reflects Paid.
- "Download Receipt" action (visible only for Paid rows): calls `GET /dues/{due_id}/receipt`, opens the returned pre-signed S3 URL in a new tab / triggers browser download. No client-side PDF rendering — always server-generated.

### 2.5 `/billing/dues`
- Same `DataTable` + status `Tabs` pattern as 2.4 but cross-cycle, with an added `Select` filter for billing cycle (optional, defaults to "All Cycles"). This is the page a treasurer lands on to "see which flats are overdue at any time" (PRD §9 user story) without drilling into a specific cycle first.

## 3. Client-side validation (zod, mirroring backend Pydantic)

```ts
export const maintenanceFormulaSchema = z.object({
  base_amount: z.coerce.number().min(0, "Must be 0 or more"),
  per_sqft_rate: z.coerce.number().min(0, "Must be 0 or more"),
  effective_from: z.coerce.date().refine(d => d >= startOfToday(), "Cannot be in the past"),
}).refine(d => d.base_amount > 0 || d.per_sqft_rate > 0, {
  message: "Both Base Amount and Per Sq.Ft. Rate are zero — every due will be ₹0. Confirm this is intentional.",
  path: ["base_amount"],
}); // soft warning, not a hard block — matches overview.md edge case 6; render as a confirm step, not a blocked submit

export const gracePeriodSchema = z.object({
  grace_period_days: z.coerce.number().int().min(0, "Must be 0 or more"),
});

export const billingCycleSchema = z.object({
  month: z.coerce.number().int().min(1).max(12),
  year: z.coerce.number().int().min(2020).max(2100),
  due_date: z.coerce.date(),
});

export const markPaidSchema = z.object({
  payment_date: z.coerce.date().refine(d => d <= new Date(), "Cannot be in the future"),
  amount_received: z.coerce.number().gt(0, "Amount received must be greater than 0"),
  payment_mode: z.enum(["cash", "bank_transfer", "cheque"]),
  reference_number: z.string().max(100).optional(),
});
```

## 4. Frontend Test Plan

### 4.1 Component tests
- Mark-paid `Dialog` rejects submit (shows validation error, does not call the API) when `amount_received` is `0` or negative.
- Mark-paid `Dialog` rejects submit when `payment_date` is in the future.
- Formula `Form` shows the "both zero" soft-warning confirm step when `base_amount = 0` and `per_sqft_rate = 0`, but still allows submit after confirmation.
- Dues `DataTable` renders the correct `Badge` variant (`success`/`warning`/`destructive`) for each of Paid/Pending/Overdue statuses — snapshot/DOM assertion on the class/token used, not just text.
- `BillingStatCards` component renders correctly with zero-value props (e.g. a brand-new tower with `pendingCount = 0`) without crashing the `NumberTicker` animation.
- Status `Tabs` correctly reflect the `?status=` query param on direct navigation (deep-linkable filter state).

### 4.2 End-to-end tests
- Admin configures a formula (base=1000, rate=2) → generates a billing cycle → dues list shows each flat's amount equal to `1000 + carpet_area × 2`, matching what Module 2's flat data reports for carpet area per flat.
- Admin marks a due as Paid → the row's badge updates to "Paid"/`success` immediately (no full page reload needed) → a "Download Receipt" link appears on that row and successfully opens a PDF.
- Admin attempts to generate a billing cycle for a month/year that already exists → sees an inline "already exists" error on the dialog, dialog does not close, no duplicate row appears in the cycles list.
- Admin generates a cycle for a tower with >300 flats → sees the "generating" progress state → list eventually shows the cycle as active with the correct total dues count once the async job completes.
- A tenant-occupied flat's due shows "Assigned To: <tenant name> (tenant)" in the dues list, but after marking it paid, the downloaded receipt shows the primary owner's name, not the tenant's.
- Flat Owner (non-admin) role viewing `/billing/dues` sees the list in read-only mode — no "Mark Paid" action visible, per `<Can permission="RECORD_PAYMENT">` gating.
- Grace period page: setting the value to `0` and saving, then navigating to a cycle with a due exactly one day past its due date, shows that due as "Overdue".
