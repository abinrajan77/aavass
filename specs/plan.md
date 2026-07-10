# Aavaas — Feature Spec Plan (v1.0)

> Master index for the Aavaas implementation specs. Source: `Aavaas - Apartment Complex
> Management_PRD_v1.3.docx`. Team: 5 full-stack developers (Next.js + FastAPI + Postgres on
> AWS RDS), one module per developer. Each module is documented as 4 files —
> `overview.md` (the contract: problem, non-goals, edge cases, acceptance criteria),
> `backend.md` (FastAPI routes, schemas, DB tables, backend test plan),
> `frontend.md` (Next.js routes, shadcn/magicui components, frontend test plan), and
> `cloud.md` (module-specific infra only — everything generic lives in `06-cloud-devops.md`).

## Read order

1. **[`00-architecture-and-standards.md`](./00-architecture-and-standards.md)** — read this first, always. Tech stack, the Navy/Gold shadcn+magicui design system, the latency-budget table, the RBAC permission catalog, and the API conventions (routing, pagination, errors, audit log, soft-delete, UUID PKs). Every module below assumes these conventions without repeating them.
2. **[`06-cloud-devops.md`](./06-cloud-devops.md)** — shared AWS plan: environments, RDS, ECS/Fargate, S3, SQS background jobs, Next.js hosting (Amplify), CI/CD, observability, security. Each module's `cloud.md` only lists what's specific to it and points back here for everything else.
3. The 5 module folders below, in dependency order.

## Module ownership & build order

| # | Module | Folder | Owns (key entities) | Depends on |
|---|---|---|---|---|
| 1 | Auth, RBAC & Tower/Complex Setup | [`01-auth-rbac-tower-setup/`](./01-auth-rbac-tower-setup/overview.md) | User, Role, Permission, AssociationMember, ApartmentComplex, Tower, `audit_log` | — (build first; everything else depends on its auth guard and tower-scoping) |
| 2 | Flat, Owner & Tenant Management | [`02-flat-owner-tenant/`](./02-flat-owner-tenant/overview.md) | Flat, Owner, FlatOwnership, Tenant (+ history) | Module 1 |
| 3 | Maintenance Billing | [`03-maintenance-billing/`](./03-maintenance-billing/overview.md) | MaintenanceFormula, GracePeriodConfig, BillingCycle, MaintenanceDue, Payment, Receipt | Modules 1, 2 |
| 4 | Special Collections & Expenditure | [`04-special-collections-expenditure/`](./04-special-collections-expenditure/overview.md) | SpecialCollection, SpecialCollectionDue, Expenditure (incl. complex-level contribution) | Modules 1, 2, 3 (reuses Module 3's payment/receipt flow via a `due_type` discriminator) |
| 5 | Reporting, Owner Portal & Notifications (v1.0 manual) | [`05-reporting-owner-portal-notifications/`](./05-reporting-owner-portal-notifications/overview.md) | Reports/exports (5 types), owner self-service dashboard, `notification_templates` | Modules 1, 2, 3, 4 (read-only aggregation layer, no new business-logic tables of its own) |

Modules 3, 4, and 5 can be built in parallel by 3 developers once 1 and 2 land, **except**
that Module 4's payment/receipt tables have a hard dependency on Module 3's schema landing
first (or at minimum, the two owners synchronizing on the `due_type` discriminator contract
in `04-special-collections-expenditure/backend.md` before either starts on payments).

This maps to PRD §12's milestones as: M1 = Modules 1+2, M2 = Module 3, M3 = Module 4, M4 =
Module 5 (+ owner portal), M5 (v1.1 automated notifications) = out of scope for this spec set.

## Cross-cutting things every module owner should know

- **Design system**: Navy (`#1E3A5F`) + Gold (`#C9A227`) shadcn theme, with `success`/`warning`/`destructive` reserved exclusively for payment status (Paid/Pending/Overdue) — never reused for other semantics (e.g. occupancy status uses `accent`/`secondary`/`muted` instead, see `02-flat-owner-tenant/frontend.md`). Full token values in `00-architecture-and-standards.md` §3.
- **Latency budgets**: every new endpoint should be checked against the table in `00-architecture-and-standards.md` §4 before shipping — if a sync endpoint can't meet its p95 at target scale, move it to the SQS-backed async job pattern in `06-cloud-devops.md` §4, don't ship a slow synchronous one.
- **RBAC**: use `require_permission("<CODE>")` (Module 1, `01-auth-rbac-tower-setup/backend.md`) on every tower-scoped route. Never write an ad-hoc role check.
- **Audit log**: any write to a financial or config record must call the shared `write_audit_log()` helper in the same DB transaction as the entity write (see `00-architecture-and-standards.md` §6 and `01-auth-rbac-tower-setup/backend.md`).
- **No hard deletes, anywhere.** Soft-delete via `deactivated_at`; immutability via `409 IMMUTABLE_RECORD`.

## Known cross-module decisions flagged during spec authoring (confirm before/while building)

These were resolved with a concrete, buildable answer in the relevant module spec, but are
genuinely not explicit in the PRD — worth a quick team sign-off rather than silent assumption:

1. **Who creates the first Tower/Complex** — resolved via a platform-level `users.is_superuser` flag, not a tenant role (`01-auth-rbac-tower-setup/overview.md`).
2. **Tenant history storage** — modeled as non-active rows in a single `tenants` table, not a separate `TenantHistory` table (`02-flat-owner-tenant/overview.md`).
3. **Formula/grace-period versioning mechanism** — append-only versioned tables with `effective_from`, snapshotted onto each `BillingCycle` at generation time (`03-maintenance-billing/overview.md`).
4. **Overdue transition** — a nightly scheduled job, not on-read computation (`03-maintenance-billing/backend.md`).
5. **Special-collection payment/receipt reuse** — a `due_type` discriminator on Module 3's `payments`/`receipts` tables rather than duplicating them (`04-special-collections-expenditure/backend.md`).
6. **Post-sale tenant-history access** — a former flat owner loses portal access entirely once their `FlatOwnership` ends; only the current owner/admin retain full history (`05-reporting-owner-portal-notifications/overview.md`).
7. **Financial-year definition** for the Collection vs Expenditure report — assumed Apr–Mar (India standard), not stated in the PRD (`05-reporting-owner-portal-notifications/backend.md`).

## Non-functional standards quick reference

| Area | Standard | Defined in |
|---|---|---|
| Page load | <3s total (FCP <1.5s, LCP <2.5s, TTI <3s) | `00-architecture-and-standards.md` §4 |
| Report generation | p50 2s, p95/hard ceiling 10s | `00-architecture-and-standards.md` §4 |
| Simple CRUD | p50 100ms, p95 200ms | `00-architecture-and-standards.md` §4 |
| Security | RBAC + argon2id password hashing + HTTPS everywhere | `00-architecture-and-standards.md` §5, `06-cloud-devops.md` §9 |
| Availability | 99% uptime target | PRD §7; `06-cloud-devops.md` (Multi-AZ RDS, min 2 ECS tasks in prod) |
| Auditability | Every financial/config write logged (who, when, before/after) | `00-architecture-and-standards.md` §6, `01-auth-rbac-tower-setup/backend.md` |
