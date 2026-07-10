# Module 4 — Cloud/Infra notes

Module-specific additions only. Everything not listed here (RDS, ECS, CI/CD, observability, security baseline) is shared infra — see `../06-cloud-devops.md`.

## S3

- Bucket: the shared `aavaas-{env}-files` bucket (per `../06-cloud-devops.md` §5) — no new bucket for this module.
- Prefix: `expenditure-attachments/{tower_id}/{expenditure_id}/{filename}` (matches the convention already listed in `../06-cloud-devops.md` §5).
- Upload pattern: backend issues a pre-signed PUT URL (10 MB max via the presigned policy's `content-length-range`, `.pdf`/`.jpg`/`.jpeg`/`.png` only via `Content-Type` condition); frontend PUTs directly to S3, never through the API server. Download: pre-signed GET URL, same as the receipt pattern.
- Receipt PDFs for special collection payments use the **existing** `receipts/{tower_id}/{receipt_id}.pdf` prefix already defined for Module 3 — this module does not add a new prefix for special-collection receipts; they are the same `Receipt` rows, same S3 path convention, differentiated only by the `due_type` field on the underlying record, not by storage location.
- Encryption/versioning/lifecycle: inherits the bucket-level SSE-S3 + versioning + no-deletion policy already defined in `../06-cloud-devops.md` §5 (financial attachments retained indefinitely, same as receipts).

## SQS / async jobs

- New job type/queue: **`special-collection-jobs`** — added alongside the existing `billing-cycle-jobs` and `report-export-jobs` queues listed in `../06-cloud-devops.md` §4. Same worker pattern: a second ECS Fargate/Celery worker service polls the queue, shares DB + S3 access with the API service.
- Trigger: `POST /api/v1/towers/{tower_id}/special-collections` when the tower's active-flat count exceeds the sync threshold (see latency budget below) — API enqueues, returns `202` + `job_id`; frontend polls `GET /api/v1/towers/{tower_id}/jobs/{job_id}` (`pending|running|done|failed`), per the shared polling convention (no websocket/SSE in v1.0).
- Idempotency key: `tower_id + special_collection_id` (the collection row is created synchronously first with `dues_generated_at = NULL`; the job's natural key ensures a retried/duplicate SQS message is a safe no-op — it only inserts dues if none already exist for that collection).

## Latency budgets (from `../00-architecture-and-standards.md` §4 — reproduced for this module's relevant rows only)

| Operation | Endpoint(s) | p50 | p95 | Notes |
|---|---|---|---|---|
| Bulk write — special collection generation | `POST /special-collections` | — | 3s sync for ≤300 flats; async job beyond that (see SQS above) | same async threshold logic as billing cycles |
| List/paginated query | `GET .../special-collections`, `.../dues`, `.../expenditures` | 200ms | 400ms | server-side pagination + indexed filters (`tower_id`, `status`, `category`) required beyond 100 rows |
| Simple CRUD (single row) | get/update expenditure, get collection detail | 100ms | 200ms | |
| Dashboard aggregates | collection rollup stats (collected/pending/overdue) | 250ms | 500ms | pre-aggregate via a single grouped query, not N+1 per-due status checks |
| PDF receipt generation | mark-paid on a special collection due | 500ms | 2s | inherited from Module 3's synchronous receipt generation — no separate budget for this module |

Everything else (RDS, ECS, CI/CD, observability) is shared — see `../06-cloud-devops.md`.
