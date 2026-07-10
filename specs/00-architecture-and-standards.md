# Aavaas — Architecture & Standards

> Shared reference for all 5 module specs (`01`–`05`) and the cloud/devops plan (`06`).
> Read this before reading any module spec — it defines the conventions every module must follow.

## 1. Tech stack

| Layer | Choice |
|---|---|
| Frontend | Next.js 14+ (App Router, TypeScript), Tailwind CSS, shadcn/ui, magicui |
| Forms/validation | react-hook-form + zod (shared schemas mirrored from backend Pydantic models where practical) |
| Data fetching | TanStack Query (React Query) over a typed fetch client; server components for initial page data, client components for interactive tables/forms |
| Backend | FastAPI (Python 3.12), Pydantic v2, SQLAlchemy 2.x (async), Alembic migrations |
| Database | PostgreSQL 16 on AWS RDS (Multi-AZ in staging/prod) |
| Auth | JWT access + refresh tokens (httpOnly cookies), FastAPI dependency-based guards |
| File storage | AWS S3 (receipt PDFs, expenditure bill/invoice attachments) |
| PDF generation | WeasyPrint or ReportLab (server-side, FastAPI) |
| Background jobs | Celery + SQS (or FastAPI `BackgroundTasks` for short jobs; SQS-backed worker for bulk billing-cycle generation — see `06-cloud-devops.md`) |
| Hosting | All-AWS: Next.js on AWS Amplify Hosting (SSR) or ECS/Fargate + CloudFront; FastAPI on ECS/Fargate behind an ALB |

Every module (`01`–`05`) is a **full-stack vertical slice**: the owning developer builds the Next.js pages, the FastAPI routes, and the DB migrations for their module end-to-end.

## 2. Module ownership

| # | Module | Spec file | Owns (entities) | Maps to PRD milestone |
|---|---|---|---|---|
| 1 | Auth, RBAC & Tower/Complex Setup | `01-auth-rbac-tower-setup.md` | User, Role, Permission, ApartmentComplex, Tower, AssociationMember | M1 (part) |
| 2 | Flat, Owner & Tenant Management | `02-flat-owner-tenant.md` | Flat, Owner, FlatOwnership, Tenant, TenantHistory | M1 (part) |
| 3 | Maintenance Billing | `03-maintenance-billing.md` | MaintenanceFormula, BillingCycle, MaintenanceDue, Payment, Receipt | M2 |
| 4 | Special Collections & Expenditure | `04-special-collections-expenditure.md` | SpecialCollection, SpecialCollectionDue, Expenditure, ComplexExpenditureContribution | M3 |
| 5 | Reporting, Owner Portal & Notifications | `05-reporting-owner-portal-notifications.md` | Report exports, Owner dashboard/context-switch, NotificationTemplate | M4 (+ v1.0 slice of M5) |

Dependency order: Module 1 must land first (auth + tenancy scoping used by all others); Module 2 next (Flat/Owner/Tenant is a dependency of 3 and 4); Modules 3, 4, 5 can then proceed in parallel, with Module 5 (reporting) trailing since it reads data produced by 3 and 4.

## 3. Design system — "Tower" theme (shadcn + magicui)

Professional, institutional, trustworthy (this app touches association money) with a warm accent for a premium, non-generic feel. Navy = primary/structure, Gold = accent/emphasis, semantic colors carry payment-status meaning throughout the app.

### 3.1 shadcn CSS variables (`app/globals.css`)

```css
:root {
  --background: 210 40% 98%;        /* #F8FAFC */
  --foreground: 217 33% 17%;        /* #1E293B */
  --card: 0 0% 100%;
  --card-foreground: 217 33% 17%;
  --popover: 0 0% 100%;
  --popover-foreground: 217 33% 17%;

  --primary: 209 54% 23%;           /* #1E3A5F deep navy */
  --primary-foreground: 210 40% 98%;

  --secondary: 210 30% 93%;
  --secondary-foreground: 209 54% 23%;

  --accent: 43 68% 47%;             /* #C9A227 warm gold */
  --accent-foreground: 26 60% 12%;

  --muted: 210 30% 93%;
  --muted-foreground: 215 16% 47%;

  --destructive: 0 72% 51%;         /* #DC2626 — Overdue */
  --destructive-foreground: 210 40% 98%;

  --success: 142 71% 35%;           /* #16A34A — Paid */
  --success-foreground: 210 40% 98%;
  --warning: 32 87% 45%;            /* #D97706 — Pending */
  --warning-foreground: 26 60% 12%;

  --border: 214 32% 88%;
  --input: 214 32% 88%;
  --ring: 209 54% 23%;
  --radius: 0.5rem;
}

.dark {
  --background: 217 47% 9%;         /* #0B1220 */
  --foreground: 210 40% 96%;
  --card: 217 40% 12%;
  --card-foreground: 210 40% 96%;
  --popover: 217 40% 12%;
  --popover-foreground: 210 40% 96%;

  --primary: 209 60% 55%;           /* brighter navy-blue for dark bg contrast */
  --primary-foreground: 217 47% 9%;

  --secondary: 217 30% 18%;
  --secondary-foreground: 210 40% 96%;

  --accent: 43 74% 55%;             /* brighter gold for dark bg */
  --accent-foreground: 26 60% 10%;

  --muted: 217 30% 18%;
  --muted-foreground: 215 20% 65%;

  --destructive: 0 72% 58%;
  --destructive-foreground: 217 47% 9%;

  --success: 142 60% 45%;
  --success-foreground: 217 47% 9%;
  --warning: 32 87% 58%;
  --warning-foreground: 26 60% 10%;

  --border: 217 30% 20%;
  --input: 217 30% 20%;
  --ring: 209 60% 55%;
}
```

`--success` / `--warning` are custom tokens (not in stock shadcn) — add matching `bg-success`, `text-success-foreground` etc. to `tailwind.config.ts` `theme.extend.colors`. Every module UI must map due/payment status to these three, never ad-hoc colors:

| Status | Token | Badge variant |
|---|---|---|
| Paid | `success` | solid green badge |
| Pending | `warning` | solid amber badge |
| Overdue | `destructive` | solid red badge |
| Vacant / Inactive | `muted` | outline gray badge |

### 3.2 Component palette (use consistently across modules)

**shadcn/ui (core, every module uses these):** `Table` + TanStack `DataTable` pattern for all list views, `Dialog` (create/edit forms in a modal for single-entity records), `Sheet` (side panel for detail views, e.g. flat/tenant detail), `Tabs` (entity sub-sections, e.g. Flat → Owners / Tenants / Billing History), `Form` (react-hook-form + zod resolver), `Badge` (status pills, per 3.1 table), `Command` (global search/switch-tower), `Calendar` + `Popover` (date pickers for due dates, lease dates), `Select`, `DropdownMenu`, `Avatar`, `Sonner` (toast notifications), `Skeleton` (loading states), `Sidebar` (primary app nav), `Breadcrumb`.

**magicui (accent components, used sparingly — dashboards and key moments, not every screen):**
- `NumberTicker` — animated counters on dashboard stat cards (total collected this month, pending dues count, overdue amount).
- `BentoGrid` — layout for the Tower Admin dashboard (stat cards + quick links in an asymmetric grid).
- `ShineBorder` — highlight the "action needed" card (e.g. overdue summary) on the admin dashboard.
- `AnimatedList` — recent activity / audit-log feed (payment recorded, formula changed, tenant added).
- `Marquee` — NOT used (no promotional content in an internal ops tool).
- `Confetti` / celebratory effects — NOT used (keep tone professional/financial).

Rule of thumb: shadcn for structure and data-density (tables, forms), magicui only on dashboard/landing surfaces to add polish without compromising the density needed for financial data screens.

## 4. Latency standards

Derived from PRD §7 NFRs ("page loads under 3 seconds; report generation under 10 seconds") broken into budgets every module's backend endpoints and frontend pages must meet at expected v1.0 scale (assume up to ~50 towers, ~500 flats/tower for load-testing baselines).

| Operation class | Example endpoints | p50 | p95 | Notes |
|---|---|---|---|---|
| Auth | login, refresh token | 150ms | 300ms | bcrypt/argon2 hashing cost tuned to stay under budget |
| Simple CRUD (single row) | get/update flat, get/update owner | 100ms | 200ms | |
| List/paginated query | list flats, list dues, list payments | 200ms | 400ms | server-side pagination + indexed filters required beyond 100 rows |
| Dashboard aggregates | admin dashboard stat cards, owner dashboard summary | 250ms | 500ms | pre-aggregate or cache (see below) if computed over >1 billing cycle |
| Bulk write — billing cycle generation | `POST /billing-cycles` (creates N due records) | — | 5s sync for ≤300 flats; async job + polling/webhook beyond that | must not block the request thread past ~5s (PRD: page loads <3s) |
| Bulk write — special collection generation | `POST /special-collections` | — | 3s sync for ≤300 flats | same async threshold logic as billing cycles |
| PDF receipt generation | `POST /dues/{id}/mark-paid` (triggers receipt) | 500ms | 2s | generate synchronously; if it regresses past 2s, move to background job + notify-on-ready |
| Report generation/export | monthly collection report, outstanding dues, CSV/PDF export | 2s | 10s (PRD hard ceiling) | large exports (>5000 rows) run as background job with download-when-ready |
| Frontend page load | any authenticated page | FCP <1.5s, LCP <2.5s, TTI <3s | — | PRD ceiling is 3s total; budgets split across FCP/LCP/TTI for testability |

Enforcement: latency budgets are captured as k6/Locust thresholds in CI-adjacent load tests (see `06-cloud-devops.md`) and as CloudWatch alarms in production. Any endpoint expected to exceed its p95 at target scale must be flagged in that module's spec and either paginated, cached, or moved to an async job — do not silently ship a slow synchronous endpoint.

## 5. RBAC model

Permissions are discrete, code-referenced constants; roles are named, configurable groupings of permissions. v1.0 ships one seeded role (`Admin`, all permissions) plus the `FlatOwner` implicit role (scoped, not permission-configurable in v1.0 UI, but modeled the same way so future roles like Secretary/Auditor need no schema change).

### 5.1 Permission catalog (v1.0)

| Permission | Description |
|---|---|
| `MANAGE_COMPLEX` | Create/edit complex & tower records |
| `MANAGE_ASSOCIATION_MEMBERS` | Add/edit association members, assign roles |
| `MANAGE_RESIDENTS` | Add/edit flats, owners, tenants |
| `CONFIGURE_BILLING` | Edit maintenance formula & grace period |
| `CREATE_BILLING_CYCLE` | Generate a billing cycle |
| `RECORD_PAYMENT` | Mark dues paid, generate receipts |
| `MANAGE_SPECIAL_COLLECTIONS` | Create/edit special collections |
| `MANAGE_EXPENDITURE` | Record tower/complex expenditure |
| `VIEW_REPORTS` | Generate/export reports |
| `VIEW_TOWER_DATA` | Read-only tower-wide visibility (flat owners get this by default) |
| `MANAGE_OWN_FLAT` | Flat owner: edit own contact/tenant/occupancy details |

### 5.2 Data model

```
permissions(id, code, description)
roles(id, tower_id, name, is_system_default)
role_permissions(role_id, permission_id)
association_members(id, tower_id, user_id, role_id, name, contact_details, created_at)
```

`Admin` role is auto-seeded per tower with all permissions on tower creation (Module 1). Flat owners are not `association_members`; they authenticate as `User` with a `flat_owner` account type and are scoped via `FlatOwnership` (Module 2), receiving `VIEW_TOWER_DATA` + `MANAGE_OWN_FLAT` implicitly — no per-tower role row needed for them in v1.0.

### 5.3 Enforcement pattern

- **Backend**: a FastAPI dependency `require_permission("RECORD_PAYMENT")` resolves the current user's tower-scoped role, checks the permission, and additionally enforces tenant isolation (`tower_id` on the path/payload must match a tower the user has access to) — every module's routers use this dependency, never ad-hoc `if user.role == "admin"` checks.
- **Frontend**: a server-side session helper exposes `session.permissions: string[]`; page-level guards live in `middleware.ts` (route-level redirect if missing base access) and component-level checks (`<Can permission="RECORD_PAYMENT">`) hide/disable actions. The frontend check is UX only — the backend dependency is the actual security boundary.

## 6. API conventions

- **Routing**: REST, tower-scoped resources nested under `/api/v1/towers/{tower_id}/...` (e.g. `/api/v1/towers/{tower_id}/flats`, `/api/v1/towers/{tower_id}/billing-cycles`). Complex-level routes under `/api/v1/complexes/{complex_id}`.
- **Pagination**: cursor-agnostic offset pagination for v1.0: `?page=1&page_size=25` (max `page_size=100`), response envelope:
  ```json
  { "items": [...], "page": 1, "page_size": 25, "total": 137 }
  ```
- **Errors**: RFC7807-style problem details:
  ```json
  { "error_code": "DUE_ALREADY_PAID", "message": "This due has already been marked as paid.", "field_errors": null }
  ```
- **Auditing**: every write to a financial or config record (formula change, grace period change, payment recorded, role/permission change) inserts an `audit_log` row. Canonical shape (extended from the earlier draft of this doc, per Module 1's build-out): `audit_log(id, tower_id NULL, user_id NULL, actor_label, action, entity_type, entity_id, before, after, created_at)` — `tower_id`/`user_id` are nullable to allow complex-level and system-generated entries (e.g. the automated overdue transition), and `actor_label` snapshots the acting user's name/email at write time so the trail stays readable after that user/association-member is later deactivated or renamed. This is a shared table/service (`write_audit_log()`, built in Module 1, imported by Modules 3 & 4 — see `01-auth-rbac-tower-setup/backend.md`).
- **Soft delete**: `deactivated_at timestamptz null` column on Flat, Owner, Tenant, AssociationMember, Role, Tower — no hard deletes, per PRD §7 Data Integrity. Immutable records (BillingCycle once dues exist, paid MaintenanceDue/SpecialCollectionDue) reject `PUT`/`DELETE` with `409 IMMUTABLE_RECORD`.
- **Multi-tenancy isolation**: every query is filtered by `tower_id` derived from the authenticated user's access, never trusted purely from the request path — the `require_permission` dependency re-validates path `tower_id` against the user's accessible towers on every request.
- **Primary keys**: every table uses a `UUID` primary key with `server_default=text("gen_random_uuid()")` (pgcrypto, native on Postgres 16/RDS) — this is set once in Module 1 and every other module follows the same convention for consistency (no auto-increment integer PKs).
- **Complex/Tower bootstrap**: `ApartmentComplex` and `Tower` records (and the platform-level `users.is_superuser` flag used to gate their creation) are owned and defined by Module 1 — see `01-auth-rbac-tower-setup/overview.md` "Design decision" and `01-auth-rbac-tower-setup/backend.md` for the table definitions and the `require_superuser()` guard, which sits alongside `require_permission()` as a second, platform-level dependency.

## 7. Cross-module notes

- Modules 3, 4, and 5 all read `Flat`/`Owner`/`Tenant` (Module 2) and `AssociationMember`/RBAC (Module 1) — treat those as read-only dependencies, do not duplicate their tables.
- Receipt PDFs (Module 3) and expenditure attachments (Module 4) both use the shared S3 upload/signed-URL pattern defined in `06-cloud-devops.md` §"File storage" — implement once, reuse.
- Special-collection payments/receipts (Module 4) reuse Module 3's `payments`/`receipts` tables and `record_payment()` service via a `due_type` discriminator (`'maintenance' | 'special_collection'`) rather than duplicating the payment/receipt flow — see `04-special-collections-expenditure/backend.md`.
- Notification message templates (Module 5) reference due/payment events produced by Modules 3 and 4 — Module 5 should consume an event/status field, not re-derive business logic already owned by those modules. The `VIEW_REPORTS` permission is reused to gate notification-preview access in v1.0 since no dedicated notifications permission exists in the catalog above — revisit if a Secretary-type role needs notification access without report access.
