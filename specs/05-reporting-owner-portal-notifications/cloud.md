# Module 5 — Cloud/Infra Notes

> Module-specific additions only. All base infra (RDS, ECS, CI/CD, observability, security) is shared — see `../06-cloud-devops.md`.

## Async report exports — `report-export-jobs` SQS queue

- Uses the shared queue defined in `06-cloud-devops.md` §4: `report-export-jobs` (AWS SQS standard queue), consumed by the shared worker ECS/Fargate service (or Celery worker) alongside `billing-cycle-jobs`.
- **Threshold**: any of the 5 report export requests (`format=pdf|csv`) that resolves to **>5000 rows** is enqueued rather than rendered inline, per the row-count check in `backend.md` §2.6.
- **Enqueue payload**: `{ "job_id", "tower_id", "report_type", "format", "params" }` — `params` is the same JSON used as the `export_jobs.params` natural key, so a retried/duplicate SQS message for an identical `(tower_id, report_type, format, params)` combination while a job is still `pending`/`running` is a safe no-op (idempotency pattern from `06-cloud-devops.md` §4).
- **Polling pattern**: the frontend polls `GET /api/v1/towers/{tower_id}/reports/export-jobs/{job_id}` every ~3s (no websocket/SSE in v1.0, consistent with the "polling is the v1.0 default" guidance in `06-cloud-devops.md` §4). Worker updates `export_jobs.status` (`pending → running → done|failed`) as it processes.
- **Worker responsibility**: query the same Postgres tables the sync path would (via the SQL patterns in `backend.md` §2), render PDF (WeasyPrint/ReportLab) or CSV, upload to S3, set `file_s3_key` and `status='done'`.

## S3 — generated export files

- Prefix: `report-exports/{tower_id}/{job_id}.{csv|pdf}`, in the same per-environment bucket (`aavaas-{env}-files`) as receipts and expenditure attachments (`06-cloud-devops.md` §5) — same SSE-S3 encryption, same pre-signed-URL access pattern (backend generates a pre-signed GET URL for the frontend to download; the frontend never receives long-lived S3 credentials).
- Lifecycle: no expiry in v1.0, consistent with the shared "financial records retained indefinitely" policy — export files move to S3 Infrequent Access after 90 days for cost, same as receipts.

## Latency budgets (from `00-architecture-and-standards.md` §4)

| Operation | p50 | p95 | Applies to |
|---|---|---|---|
| Dashboard aggregates | 250ms | 500ms | `/owners/me/flats/{flat_id}/dashboard`, `/owners/me/flats-summary` |
| Report generation/export (≤5000 rows, sync) | 2s | 10s (hard ceiling) | all 5 report endpoints, both JSON preview and `format=pdf|csv` |
| Report export (>5000 rows, async) | — | job enqueue itself must return in ~200ms; total time-to-file-ready is not latency-budgeted the same way (background) but should be monitored via SQS age-of-oldest-message alarms | all 5 report endpoints beyond the row threshold |

If a report's JSON preview or sync export regresses past its p95 at target scale (~50 towers, ~500 flats/tower), lower the async threshold below 5000 rows or add server-side pagination to the preview table before shipping — do not let it silently exceed the PRD §7 "report generation under 10 seconds" ceiling.

Everything else (RDS, ECS, CI/CD, observability) is shared — see `../06-cloud-devops.md`.
