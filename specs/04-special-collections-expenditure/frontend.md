# Module 4 — Frontend

Next.js 14+ (App Router, TypeScript), Tailwind, shadcn/ui, magicui (accent only) — per `../00-architecture-and-standards.md` §1 and §3. Forms: react-hook-form + zod, mirroring backend Pydantic constraints. Data fetching: TanStack Query over the typed fetch client; server components for initial page data, client components for interactive tables/forms/dialogs.

## Routes

| Route | Purpose | Access |
|---|---|---|
| `/towers/[towerId]/special-collections` | List of special collections for the tower, with an "open collections" summary | Admin: full; Flat Owner: read-only, own-flat dues only |
| `/towers/[towerId]/special-collections/[id]` | Collection detail — rollup stats + dues `DataTable` + mark-paid action | Admin: full; Flat Owner: sees only their own due row(s) within the collection |
| `/towers/[towerId]/expenditures` | Expenditure list (regular + complex-contribution rows, filterable) | Admin: full (create/edit/delete); Flat Owner: read-only (per PRD §6.5.1) |
| `/towers/[towerId]/expenditures/new?type=complex-contribution` | Create form — `type` query param switches the same route/component between the regular-expenditure schema and the complex-contribution schema | Admin only (`MANAGE_EXPENDITURE`) |

`middleware.ts` route guards: `/expenditures/new` redirects flat owners away (no `MANAGE_EXPENDITURE`); `/special-collections` create dialog trigger is hidden client-side via `<Can permission="MANAGE_SPECIAL_COLLECTIONS">` but the actual boundary is the backend dependency, per §5.3.

## shadcn components

- **`/special-collections` list page**: `DataTable` (TanStack pattern per §3.2) with columns Title, Total Amount, Due Date, Collected/Total progress, Status derived-`Badge` (`open` = outline, or reuse `Pending`/`Paid` semantics per-collection at the aggregate level using `warning`/`success` tokens once fully collected). `Dialog` + `Form` for "Create Special Collection" — fields: Title (`Input`), Description (`Textarea`, optional), Total Amount (`Input type=number`), Due Date (`Calendar` + `Popover`), Split Basis (`Select`, single option `Equal Split` in v1.0, disabled/locked — visually communicates future extensibility without offering a broken choice). A **live preview panel** inside the dialog recalculates `perFlatAmount = totalAmount / activeFlatCount` (fetched via a lightweight `GET .../flats?status=active&count_only=true` or reused from Module 2's active-flat count) and renders "≈ ₹{perFlatAmount} per flat across {activeFlatCount} flats" — reactive to the `total_amount` field via `watch()` from react-hook-form, updates on every keystroke (debounced 200ms).
- **`/special-collections/[id]` detail page**: stat cards (Collected, Pending, Overdue counts/amounts) using `NumberTicker` per §3.2 magicui guidance for the headline collected-amount figure; `Tabs` not required (single dues table is the primary content); dues `DataTable` reusing **the exact same status-`Badge` pattern Module 3 uses** for maintenance dues (`Paid`→`success` solid, `Pending`→`warning` solid, `Overdue`→`destructive` solid) — do not invent a new badge variant for special collection status, import/reuse Module 3's `<DueStatusBadge status={...} />` component if it is extracted as shared, or replicate its exact class mapping if not yet extracted. "Mark Paid" row action opens a `Dialog` with the payment form (Payment Date `Calendar`+`Popover`, Amount `Input`, Mode `Select`, Reference `Input` optional) — same fields/shape as Module 3's mark-paid dialog, reused/copied verbatim for UX consistency (this is a payment on the same underlying `payments` table).
- **`/expenditures` list page**: `DataTable` with columns Date, Category (`Badge`, neutral/`secondary` variant — no payment-status semantics apply here), Description, Vendor/Payee, Amount, Attachment (icon-link if present), Complex Contribution (small tag/`Badge` if `is_complex_contribution=true`). Filter bar: Category `Select`, date range `Calendar` (range mode), "Complex Contribution only" toggle (shadcn `Switch` or checkbox in a `DropdownMenu` filter).
- **`/expenditures/new`**: `Form` with `Select` for Category (options: Cleaning / Security / Repairs / Utilities / Other; disabled+defaulted to "Other" when `type=complex-contribution` but still editable), `Input` for Vendor/Payee Name (required), `Input type=number` for Amount, `Select` for Payment Mode, `Calendar`+`Popover` for Date, and a file upload control — shadcn-compatible `Input type="file"` styled per the design system, accepting `.pdf,.jpg,.jpeg,.png`, showing filename + size + a client-side progress indicator once the pre-signed PUT starts. When `type=complex-contribution`: an extra `Input type=number` for "Total Complex Expense Amount (optional, for reference)" appears above the "Tower's Share Amount" field (which replaces the generic "Amount" label), with helper text: "Only the tower's share posts to this tower's books."

## magicui use (minimal, per §3.2 rule of thumb)

- `ShineBorder` on the "Open Special Collections" summary card at the top of `/special-collections` (the one card that represents "action needed" / money still to be collected) — this is the only magicui accent in this module, consistent with the "sparingly, dashboard/key-moments only" guidance. No `BentoGrid`, `AnimatedList`, `Marquee`, or `Confetti` in this module — expenditure/collection screens are data-dense working screens, not a dashboard landing page (that's Module 5's owner-portal dashboard).

## Client validation (zod)

```typescript
const specialCollectionSchema = z.object({
  title: z.string().min(1, "Title is required").max(200),
  description: z.string().optional(),
  total_amount: z.coerce.number().positive("Total amount must be greater than 0"),
  split_basis: z.literal("equal"),
  due_date: z.date().refine((d) => d > new Date(), "Due date must be in the future"),
});

const markPaidSchema = z.object({
  payment_date: z.date(),
  amount_received: z.coerce.number().positive(),
  payment_mode: z.enum(["cash", "bank_transfer", "cheque"]),
  reference_number: z.string().optional(),
});

const MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024; // 10 MB — matches backend presigned policy
const ACCEPTED_ATTACHMENT_TYPES = ["application/pdf", "image/jpeg", "image/png"];

const expenditureSchema = z.object({
  expenditure_date: z.date(),
  category: z.enum(["cleaning", "security", "repairs", "utilities", "other"]),
  description: z.string().min(1, "Description is required"),
  vendor_payee_name: z.string().min(1, "Vendor/payee name is required"),
  amount: z.coerce.number().positive("Amount must be greater than 0"),
  payment_mode: z.enum(["cash", "bank_transfer", "cheque"]),
  attachment: z
    .instanceof(File)
    .optional()
    .refine((f) => !f || f.size <= MAX_ATTACHMENT_BYTES, "File must be under 10 MB")
    .refine((f) => !f || ACCEPTED_ATTACHMENT_TYPES.includes(f.type), "Only PDF, JPEG, or PNG files are allowed"),
});

const complexContributionSchema = expenditureSchema.extend({
  complex_total_amount: z.coerce.number().positive().optional(),
  amount: z.coerce.number().positive("Tower's share amount must be greater than 0"),
});
```

## Frontend Test Plan

**e2e (Playwright, against a seeded dev/staging environment):**

1. **Live per-flat split preview.** Creating a special collection with `total_amount=100000` on a tower fixture with 20 active flats shows "≈ ₹5,000.00 per flat across 20 flats" in the dialog preview before submit — verify it updates reactively when `total_amount` changes to a value that produces a non-even split (e.g. `100005` → mostly ₹5,000.25 with a few flats at ₹5,000.26, matching the backend's remainder-distribution rule) without needing to submit the form.
2. **Special collection created while a tenant is on record still assigns the owner.** With a fixture flat that has an active tenant, create a special collection, open the collection detail dues table, and assert the due row's "Responsible Party" column shows the owner's name, not the tenant's.
3. **Skipped-flat warning surfaces in the UI.** With a fixture flat that has no active owner, create a special collection and assert a post-creation toast/banner lists the skipped flat number and reason, and the dues table shows one fewer row than total active flats.
4. **Mark-paid flow generates and links a receipt.** From the collection detail dues table, mark a pending due paid; assert the row's status badge flips to `Paid` (success/green) and a "View Receipt" link appears that opens the pre-signed PDF URL.
5. **Uploading an expenditure attachment over the size limit shows a validation error before submit.** On `/expenditures/new`, attach a file >10 MB; assert the inline field error appears immediately (no network call for the presigned URL is made) and the Submit button remains disabled or submission is blocked.
6. **Complex-contribution form only posts the tower's share to the ledger.** Submit `/expenditures/new?type=complex-contribution` with `complex_total_amount=500000` and tower's share `80000`; on the resulting `/expenditures` list, assert the row's displayed Amount is `80000.00` and the category-totals summary reflects only that figure.
7. **Multiple open collections render independently.** With two open special collections seeded on the same tower, the `/special-collections` list shows both with independent progress bars/collected-amount figures, and navigating into each shows only its own dues.

**Component tests (Vitest/RTL):**

1. **Expenditure form requires vendor/payee name and rejects empty submission.** Submitting with `vendor_payee_name` empty shows the zod error message and does not fire the create mutation.
2. **Due-date-in-future validation on special collection form.** Selecting a past date for `due_date` blocks submission with the expected error message.
3. **Attachment file-type rejection.** Selecting a `.docx` file shows "Only PDF, JPEG, or PNG files are allowed" and blocks submission.
4. **Status badge mapping matches Module 3's convention.** A due with `status="overdue"` renders the shared `destructive`/red badge variant, `"paid"` renders `success`/green, `"pending"` renders `warning`/amber — snapshot-test against the same class names Module 3's `DueStatusBadge` uses, to catch drift if either module's badge component is edited independently.
5. **Complex-contribution field toggle.** Rendering the expenditure form with `type=complex-contribution` shows the "Total Complex Expense Amount (optional)" field and relabels "Amount" to "Tower's Share Amount"; rendering without the query param hides that extra field entirely.
