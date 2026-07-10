# Module 3 — Maintenance Billing — Cloud/Infra Notes

> This module is the primary consumer of the shared SQS job pattern and S3 file-storage pattern defined in `../06-cloud-devops.md`. This file only records the module-specific parameters — it is not a restatement of the shared plan.

## SQS — bulk billing-cycle generation

- Queue: `billing-cycle-jobs` (per `06-cloud-devops.md` §4 — one queue per job type, standard SQS queue).
- Idempotency key: `tower_id + month + year` (matches the `UNIQUE (tower_id, month, year)` constraint on `billing_cycles` — a retried/duplicate SQS message for the same key is a safe no-op, see `backend.md` §4/§6.3).
- Trigger condition: `POST /api/v1/towers/{tower_id}/billing-cycles` enqueues to this queue only when the tower's active flat count exceeds ~300 (below that, generation runs synchronously in the request); see the latency table below.
- Client pattern: API returns `202 Accepted` + `job_id`; frontend polls the shared canonical route `GET /api/v1/towers/{tower_id}/jobs/{job_id}` (`pending|running|done|failed`) — no websocket/SSE in v1.0, per the shared default. This is the same route Modules 4 and 5 poll for their own job types; do not build a module-specific job-status endpoint.
- Worker: same shared ECS Fargate worker service described in `06-cloud-devops.md` §4, sharing DB + S3 access with the API service.

## S3 — receipt PDFs (shared with Module 4)

- Bucket: shared per-environment bucket `aavaas-{env}-files` (per `06-cloud-devops.md` §5).
- Prefix/key: `receipts/{tower_id}/{receipt_id}.pdf` — one object per receipt, immutable once written (never overwritten; a due can only be paid/receipted once, see `backend.md` §1.6). This same prefix/table is used for special-collection receipts too (Module 4) — there is no separate `special-collection-receipts/` prefix.
- Access: backend generates a pre-signed **GET** URL (15 min expiry) for `GET /api/v1/towers/{tower_id}/dues/{due_id}/receipt` downloads (or Module 4's equivalent special-collection-due route); the frontend never receives long-lived S3 credentials. No pre-signed PUT needed for this module (receipts are server-generated PDFs uploaded directly by the API/worker, not user-uploaded files).
- Encryption/versioning/lifecycle: inherits the shared bucket defaults (SSE-S3, versioning on, no expiry — retained indefinitely per PRD §7 auditability).

## Latency budgets this module must meet

(Copied from `00-architecture-and-standards.md` §4 for quick reference — that table is the source of truth if this ever drifts.)

| Operation | p50 | p95 | Notes |
|---|---|---|---|
| Bulk write — billing cycle generation (`POST /billing-cycles`) | — | 5s sync for ≤300 flats; async job (SQS `billing-cycle-jobs`) + polling beyond that | must not block the request thread past ~5s |
| PDF receipt generation (`PATCH /dues/{id}/mark-paid`) | 500ms | 2s | generate synchronously; move to background job + notify-on-ready only if this regresses past 2s in practice |
| List/paginated query (dues list, cycles list) | 200ms | 400ms | server-side pagination + indexed filters (`status`, `due_date`, denormalized `tower_id` on `maintenance_dues`) required |
| Dashboard aggregates (billing stat cards) | 250ms | 500ms | pre-aggregate or cache if computed over more than one billing cycle |

Everything else (RDS, ECS, CI/CD, observability) is shared — see `../06-cloud-devops.md`.
