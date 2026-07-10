# Aavaas — Cloud & DevOps Plan (Shared)

> All-AWS deployment. This is the shared infrastructure plan referenced by every module spec —
> module owners should not need to make infra decisions, only consume what's defined here
> (env vars, S3 bucket/prefix conventions, job queue).

## 1. Environments

| Env | Purpose | AWS account/isolation | DB | Notes |
|---|---|---|---|---|
| `dev` | Shared developer integration | Single AWS account, `dev` VPC | RDS `db.t4g.micro`, single-AZ | Reset/seed data weekly; auto-shuts down nights/weekends to save cost |
| `staging` | Pre-prod validation, PRD acceptance testing | Same account, `staging` VPC | RDS `db.t4g.small`, single-AZ | Mirrors prod config, smaller instance sizes |
| `prod` | Live | Same account (or separate prod account if org policy requires), `prod` VPC | RDS `db.r6g.large` (start), **Multi-AZ** | Deletion protection on, automated backups, PITR enabled |

Each environment gets its own VPC with public subnets (ALB, NAT) and private subnets (ECS tasks, RDS) — RDS and ECS tasks never sit in a public subnet.

## 2. Database — AWS RDS PostgreSQL

- Engine: PostgreSQL 16, RDS (not Aurora, for v1.0 — revisit if read-replica scaling becomes necessary post-launch).
- Multi-AZ enabled in `staging` (optional) and required in `prod`.
- Automated backups: 7-day retention `dev`/`staging`, 35-day retention + PITR `prod`.
- Parameter group: `log_min_duration_statement = 500ms` in prod to catch slow queries against the latency budgets in `00-architecture-and-standards.md` §4.
- Connections: FastAPI uses SQLAlchemy async engine with a bounded pool (`pool_size=10, max_overflow=20` per ECS task) — do not open unpooled connections from Lambda/scripts against prod RDS.
- Migrations: Alembic, run as a one-off ECS task (or CI job step) **before** the new app version is allowed to receive traffic — never auto-migrate on app boot in prod.
- Credentials: stored in AWS Secrets Manager, injected into ECS task definitions as secrets (never as plain env vars, never committed).

## 3. Backend — FastAPI on ECS/Fargate

- Containerized (multi-stage Dockerfile: build deps → slim runtime image).
- ECS Fargate service behind an Application Load Balancer; health check on `GET /healthz` (checks DB connectivity).
- Autoscaling: target-tracking on ECS service CPU (target 60%) and ALB request count per target; min 2 tasks in `prod` for zero-downtime deploys, min 1 in `dev`/`staging`.
- Deploys: rolling update (ECS native), min healthy percent 100 / max percent 200 in `prod` to avoid downtime.
- Secrets/config: DB URL, JWT signing key, S3 bucket names, SQS queue URL — all via Secrets Manager / SSM Parameter Store, referenced in the task definition.

## 4. Background jobs — bulk billing/report generation

Per `00-architecture-and-standards.md` §4, any operation exceeding its sync latency budget (billing-cycle generation beyond ~300 flats, large report exports) runs as an async job, not inline in the request:

- Queue: AWS SQS (standard queue), one queue per job type (`billing-cycle-jobs`, `report-export-jobs`).
- Worker: a second ECS Fargate service (or Celery worker container) polling SQS, sharing the same DB and S3 access as the API service.
- Client pattern: API enqueues the job and returns `202 Accepted` with a `job_id`; frontend polls a **single canonical route shared by every module and job type**: `GET /api/v1/towers/{tower_id}/jobs/{job_id}` → `{ "job_id", "job_type", "status": "pending|running|done|failed", "result": {...} | null, "error_message": string | null }`. `job_type` distinguishes `billing_cycle`, `special_collection`, `report_export`, etc. so one frontend polling hook/component works for all of them — no module should invent its own job-status path (e.g. not `/api/v1/jobs/{job_id}` without a tower prefix, not a report-specific `/reports/export-jobs/{job_id}`). No websocket/SSE in v1.0 — polling is the default, keep it simple.
- Idempotency: job payload includes a natural key (e.g. `tower_id + month + year` for billing cycles) so a retried/duplicate message is a safe no-op.

## 5. File storage — S3

- One bucket per environment (`aavaas-{env}-files`), prefixed by module: `receipts/{tower_id}/{receipt_id}.pdf`, `expenditure-attachments/{tower_id}/{expenditure_id}/{filename}`.
- Access pattern: backend generates a pre-signed PUT URL for uploads (expenditure attachments) and pre-signed GET URLs for downloads (receipts, attachments) — the frontend never gets long-lived S3 credentials.
- Encryption: SSE-S3 (AES-256) by default; versioning enabled to protect against accidental overwrite of a receipt PDF.
- Lifecycle: no expiry in v1.0 (financial records are retained indefinitely per PRD auditability requirement); move to S3 Infrequent Access after 90 days for cost, no deletion.

## 6. Frontend — Next.js hosting

- **AWS Amplify Hosting** for the Next.js app (SSR support, built-in CI from the git branch, per-environment domains: `dev.aavaas.app`, `staging.aavaas.app`, `app.aavaas.app`).
- Alternative (if Amplify's SSR runtime proves limiting for a given feature): containerize Next.js and run it as its own ECS/Fargate service behind the same ALB pattern as the API, with CloudFront in front for static asset caching. Default to Amplify for v1.0; only switch if a concrete limitation is hit.
- Environment variables (API base URL, public config) managed per Amplify environment/branch; secrets never exposed to the client bundle — only `NEXT_PUBLIC_*` values that are genuinely safe to ship to the browser.

## 7. CI/CD

GitHub Actions, one pipeline per repo (assume a `frontend` repo and a `backend` repo, or a monorepo with path-based triggers):

**Backend pipeline** (on PR): lint (ruff) → type check (mypy) → unit tests (pytest) → build Docker image → (on merge to `main`) push image to ECR → run Alembic migration task against target env → deploy new ECS task definition.

**Frontend pipeline** (on PR): lint (eslint) → type check (tsc) → unit tests (vitest/jest) → build → (on merge) Amplify auto-deploys from the connected branch.

**Gating**: PRs require passing lint/typecheck/tests before merge; `staging` deploys automatically on merge to `main`; `prod` deploy is a manual promotion step (tag-based) requiring one approval, per the "confirm before affecting shared systems" norm for production changes.

## 8. Observability

- **Logs**: structured JSON logs from FastAPI (request id, user id, tower id, latency) shipped to CloudWatch Logs; Next.js server logs likewise.
- **Metrics/alarms**: CloudWatch alarms on (a) ALB p95 latency exceeding the budgets in `00-architecture-and-standards.md` §4 per route class, (b) ECS service CPU/memory saturation, (c) RDS CPU/connections/free storage, (d) SQS queue depth/age-of-oldest-message (signals a stuck worker).
- **Audit trail**: the `audit_log` table (defined in `00-architecture-and-standards.md` §6) is the system of record for financial/config changes per PRD §7 Auditability — CloudWatch/observability tooling is for operational health, not a substitute for that table.
- **Error tracking**: Sentry (or CloudWatch + X-Ray if preferring to stay AWS-native) for both frontend and backend exception capture.

## 9. Security

- HTTPS everywhere via ACM certificates on the ALB and CloudFront/Amplify — no plain HTTP listener except redirect-to-HTTPS.
- AWS WAF on the ALB/CloudFront: rate-limiting rule + managed rule set (SQLi/XSS common protections) as a baseline, not a replacement for input validation in FastAPI/Pydantic.
- IAM: least-privilege task roles per ECS service (API task role can read/write its S3 prefixes and its SQS queues only; worker task role likewise scoped) — no wildcard `s3:*`/`sqs:*`.
- Secrets rotation: RDS credential rotation via Secrets Manager automatic rotation (Lambda rotation function) on a 90-day cycle in `prod`.
- Passwords: argon2id hashing (per PRD §7 "salted hashes" requirement — argon2id is the modern equivalent), never reversible encryption.

## 10. Cost/scale baseline

Sizing above targets v1.0 scale (tens of towers, hundreds of flats each) — this is a starting point, not a hard ceiling. Revisit RDS instance class and ECS task count based on actual staging load-test results before the `prod` launch milestone (M4 per PRD §12).
