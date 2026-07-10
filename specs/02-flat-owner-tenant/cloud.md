# Module 2 — Flat, Owner & Tenant Management: Cloud/DevOps Notes

> Companion files: [`overview.md`](./overview.md) · [`frontend.md`](./frontend.md) · [`backend.md`](./backend.md)

No module-specific infra beyond `../06-cloud-devops.md`. This module has no file uploads, no async/background
jobs, and no bespoke S3/SQS usage — it is synchronous CRUD backed by RDS Postgres, well within the "Simple CRUD"
and "List/paginated query" latency budgets in `../00-architecture-and-standards.md` §4 (flat/owner/tenant list and
detail endpoints should sit at p95 200–400ms per that table; no endpoint here approaches the async-job threshold).

Everything else (RDS, ECS, CI/CD, observability) is shared — see `../06-cloud-devops.md`.
