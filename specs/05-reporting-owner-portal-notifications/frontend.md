# Module 5 — Frontend

> Next.js (App Router), shadcn/ui + magicui per `../00-architecture-and-standards.md` §3. This is the most dashboard-heavy module in the app — lean on magicui more deliberately than Modules 1–4, but never at the cost of data density on the report/table screens.

## 1. Routes

| Route | Who | Purpose |
|---|---|---|
| `/towers/[towerId]/reports` | Admin (`VIEW_REPORTS`) | Tabs across the 5 report types, shared period/date-range picker, preview table, export buttons |
| `/towers/[towerId]/notifications/preview/[dueId]` | Admin (`VIEW_REPORTS`) | Notification message preview/copy screen for a specific due + event |
| `/my-flats` | Flat Owner | Owner-portal landing — tower/flat picker (Command palette if >1 tower) |
| `/my-flats/[flatId]/dashboard` | Flat Owner | Scoped BentoGrid dashboard for one flat |

Route guards: `middleware.ts` redirects non-owners away from `/my-flats/*` and non-`VIEW_REPORTS` users away from `/towers/*/reports` and `/towers/*/notifications/*`, per `00-architecture-and-standards.md` §5.3 (frontend check is UX only, backend `require_permission`/ownership dependency is the real boundary).

## 2. `/towers/[towerId]/reports`

- **`Tabs`** (shadcn) across the 5 report types: Monthly Collection, Outstanding Dues, Expenditure, Collection vs Expenditure, Tenant Register. Tab state in the URL (`?tab=collection`) so a link to a specific report is shareable/bookmarkable.
- Shared period control above the tabs, rendered contextually per tab:
  - Collection: `Select` bound to the tower's `BillingCycle` list (Module 3 data) — no raw date-range needed, cycles are the natural unit.
  - Outstanding Dues: `Calendar` + `Popover` for an optional "as of" date (defaults to today).
  - Expenditure: `Calendar` range picker (`period_start`/`period_end`).
  - Collection vs Expenditure: `Select` for `period_type` (Month / Financial Year) + a `Select` for month/year or FY.
  - Tenant Register: no period control (point-in-time register).
- **`DataTable`** (TanStack + shadcn `Table` pattern, per `00-architecture-and-standards.md` §3.2) renders the JSON preview (endpoint called without `format`) before export — sortable columns, client-side pagination for the preview (server already caps preview fetch reasonably; full export always goes through the file endpoints, not the preview payload).
  - Status columns (Paid/Pending/Overdue) use the shared `Badge` variant mapping from §3.1 of the architecture doc — never ad-hoc colors.
  - Empty state: when `items` is `[]`, render a centered `<EmptyState>` message ("No dues for this billing cycle yet." / "No expenditures recorded for this period.") — never an empty `<Table>` shell, never an error toast.
- Two export buttons ("Export PDF", "Export CSV") call the same endpoint with `format=pdf|csv`:
  - If response is a file (≤5000 rows): trigger browser download directly.
  - If response is `202 { job_id }`: switch the buttons to a disabled "Preparing export…" state with a `Skeleton` shimmer, poll `GET .../export-jobs/{job_id}` every 3s (TanStack Query `refetchInterval`), and on `status: done` trigger the download from the returned pre-signed URL and show a `Sonner` toast ("Export ready"); on `failed`, toast an error with a retry action.

## 3. `/towers/[towerId]/notifications/preview/[dueId]`

Reached from a "Notify" action button on Module 3/4's due detail views (out of this module's ownership to build the button itself, but this module owns the destination screen and must accept `?event=due_generated|overdue_reminder|payment_confirmed&due_type=maintenance|special_collection` query params).

- `AnimatedList` (magicui) renders the drafted message(s) as a queue — one card per recipient. For a tenant-occupied flat this shows exactly 2 cards (tenant, then owner copy, in that order); for owner-occupied, exactly 1 card. Each card:
  - Recipient name + phone number (header)
  - Rendered message text in a monospace-ish readable block
  - A "Copy" button (`navigator.clipboard`) with a `Sonner` toast confirmation ("Copied to clipboard")
- No send/dispatch button anywhere on this screen — the copy affordance is the entire v1.0 interaction, consistent with the Non-goal (no automated dispatch).
- If the due has no resident resolved (defensive/edge case), render an inline error state instead of a card, matching the backend's `422`.

## 4. `/my-flats` (owner landing)

- If the authenticated owner has flats in exactly one tower: redirect straight to that tower's default flat dashboard (`/my-flats/[flatId]/dashboard`) — no picker friction for the common case.
- If multiple towers: render a `Command` palette (shadcn, magicui-adjacent styling) as the primary switcher — grouped by tower name, each item a flat (flat number + occupancy badge). Selecting an item navigates to `/my-flats/[flatId]/dashboard`.
- The Command palette is also reachable from a persistent header control on every `/my-flats/*` page (not just the landing) so switching context doesn't require returning to `/my-flats` first — critical for the "owner with flats in 3 towers switches context" edge case in `overview.md`.

## 5. `/my-flats/[flatId]/dashboard`

`BentoGrid` (magicui) layout, asymmetric grid of cards:

- **Large cell — Current due status**: Card with `Badge` (Paid/Pending/Overdue, shared status-color mapping) showing this cycle's due amount and date. If status is `overdue`, wrap this card in `ShineBorder` (magicui) — the "action needed" highlight, consistent with how the admin dashboard uses `ShineBorder` for its own overdue summary per `00-architecture-and-standards.md` §3.2, so the visual language is consistent for the same underlying meaning (overdue = needs attention) across both admin and owner surfaces.
- **Stat cells — YTD totals**: `NumberTicker` (magicui) for "Total Paid YTD" and "Total Due YTD", animating up from 0 on mount, sourced from `ytd_totals` in the dashboard response.
- **Payment history cell**: compact `DataTable` (paginated, most recent first) — clicking a row opens a `Sheet` with that due's detail and a receipt download link if paid.
- **Receipts cell**: list of receipt cards, each with a "Download PDF" action (pre-signed S3 GET URL from Module 3, this module just surfaces the link returned by its own `dashboard` endpoint).
- **Tower expenditures cell**: compact `DataTable` (read-only, current FY by default with a period `Select` to widen), reusing the same table shape as the admin Expenditure report tab for visual consistency.
- **Tenant history cell**: `Tabs` for "Current" / "Past" tenants, each a small list (name, phone, lease dates). Rendered even for a flat with no current tenant (owner-occupied) — shows past tenants only, or an empty state ("No tenant history for this flat.") if none.
- **Own-flat edit affordance**: an "Edit contact / tenant / occupancy" button opening a `Dialog`+`Form` (react-hook-form + zod) — this posts to Module 2's owner-writable endpoints, not owned by this module, but the entry point lives on this dashboard per PRD §6.6 ("they can update... their flat's tenant information, and occupancy status").

Card reuse note: `Card` + `Badge` components and the status-color tokens are the same ones defined for Module 3's due-status displays — this module must not redefine its own badge variants.

## Frontend Test Plan

- **e2e**: owner with flats in 2 towers logs in, lands on `/my-flats`, opens the Command palette, switches to Tower B's flat, and the dashboard reloads showing only Tower B's due/payment/receipt/expenditure/tenant data — no stale Tower A figures visible during or after the transition (assert on a Tower-A-only sentinel value being absent post-switch).
- **e2e**: owner with a flat in exactly one tower is redirected straight from `/my-flats` to that flat's dashboard without seeing a picker.
- **e2e**: admin generates the Collection vs Expenditure summary for a month with recorded collections but zero expenditures — page shows `total_expenditure: 0` and an explicit "No expenditures recorded for this period" empty state in the expenditure breakdown area, not a spinner stuck loading or an error banner.
- **e2e**: admin triggers a CSV export that the backend resolves to >5000 rows — UI shows the "Preparing export…" state, polls, and auto-downloads the file once the job completes, without the admin needing to manually refresh.
- **e2e**: admin opens the notification preview for a tenant-occupied flat's overdue due — sees exactly 2 message cards (tenant, owner copy) in the `AnimatedList`, each independently copyable; for an owner-occupied flat's due, sees exactly 1 card.
- **component**: notification preview screen shows two distinct message cards only when `messages.length === 2` in the API response — snapshot test asserts card count matches recipient count, and that no send/dispatch button is rendered under any state.
- **component**: report `DataTable` renders the shared status `Badge` variants (success/warning/destructive) matching the exact tokens from `00-architecture-and-standards.md` §3.1 — regression test against a hard-coded color swatch to catch drift from ad-hoc colors.
- **component**: owner dashboard's `NumberTicker` cells render the correct final value (post-animation) matching `ytd_totals` from a mocked API response.
- **visual/a11y**: `ShineBorder` on the overdue "action needed" card does not reduce text contrast below WCAG AA against both light and dark theme tokens (per the dual-theme requirement inherited from the design system).
