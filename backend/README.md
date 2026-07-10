# Aavaas Backend — Module 1 (Auth, RBAC & Tower/Complex Setup) + Module 4 (Special Collections & Expenditure)

FastAPI (Python 3.12) service implementing Module 1 of the Aavaas spec set: login/JWT auth,
the RBAC engine (permissions/roles/association members), `ApartmentComplex`/`Tower` CRUD,
and the shared `audit_log` write helper other modules import.

See `../specs/01-auth-rbac-tower-setup/` for the full spec (`overview.md`, `backend.md`,
`cloud.md`) this implementation follows.

Also implements the dependency-free slice of Module 4 (Special Collections & Expenditure —
`special_collections`/`special_collection_dues`/`expenditures`, equal-split due generation,
expenditure CRUD, S3 attachment upload/download) — see "Module 4" under "Known deviations /
stubs" below for exactly what is and isn't included, and
`../specs/04-special-collections-expenditure/backend.md` for the full spec.

## Requirements

- Python 3.12
- Docker + Docker Compose (for local Postgres, and for running the integration test suite
  via `testcontainers-python` — see "Running tests" below)

## Local setup

```bash
# 1. Start Postgres (from the repo root, one level up from backend/)
cd ..
docker compose up -d postgres

# 2. Python environment
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 3. Configure environment
cp .env.example .env
# edit .env if your local Postgres isn't on the default host/port/credentials

# 4. Run migrations (creates all tables + seeds the 11-permission catalog)
alembic upgrade head

# 5. Run the API
uvicorn app.main:app --reload
```

The API is served at `http://localhost:8000`; interactive docs at `/docs`. Health check:
`GET /api/v1/healthz` (verifies DB connectivity).

### Creating the first superuser

There is no signup flow (per spec, v1.0 has no self-service registration). To bootstrap the
very first platform superuser (who can then create the first `ApartmentComplex`/`Tower`),
insert a row directly, e.g.:

```sql
-- Generate a password hash first: `python -c "from app.services.security import hash_password; print(hash_password('your-password'))"`
INSERT INTO users (email, hashed_password, account_type, is_superuser)
VALUES ('ops@aavaas.internal', '<argon2id-hash>', 'tower_admin', true);
```

## Running tests

```bash
source .venv/bin/activate
pytest
```

Tests use a **real PostgreSQL instance via `testcontainers-python`** — the suite starts a
disposable `postgres:16` container per test session (schema created + permission catalog
seeded once), and every test runs inside a rolled-back transaction for isolation. This
requires Docker to be reachable from wherever `pytest` runs (Docker-in-Docker works fine in
this repo's dev/CI sandbox — verified with a plain `docker ps` before this suite was built).

**Fallback if Docker-in-Docker isn't available in some future environment**: point the suite
at the docker-compose Postgres service instead of testcontainers. This repo does not
implement that fallback in code (testcontainers works here), but the manual steps are:

1. `docker compose up -d postgres` (from the repo root) and create a dedicated test database,
   e.g. `CREATE DATABASE aavaas_test OWNER aavaas; \c aavaas_test; CREATE EXTENSION pgcrypto;`
2. Swap `tests/conftest.py`'s `postgres_container`/`database_url` fixtures for one that simply
   returns `postgresql+asyncpg://aavaas:aavaas@localhost:5432/aavaas_test` and runs the same
   `Base.metadata.create_all` + permission-seed step once per session.
3. Run `pytest` as usual — the rest of the suite (fixtures, factories, tests) is unchanged.

### Test layout

- `tests/unit/` — pure dependency/service-level tests (permission allow/deny, tower-access
  edge cases, superuser bypass, TOWER_INACTIVE-on-mutate-vs-read, argon2id hashing, refresh
  token rotation/reuse-detection, last-admin-guard counting logic) — still exercised against
  a real DB session (no mocking), just without going through HTTP routing.
- `tests/integration/` — full HTTP request/response tests via `httpx.AsyncClient` against the
  actual FastAPI app (cross-tower isolation incl. under pagination, audit log correctness +
  atomicity, association-member email-linking, role immutability/`ROLE_IN_USE`/`LAST_ADMIN`
  guards, tower deactivate/reactivate, full login→refresh→logout cycle, complex/tower
  bootstrap seeding all 11 permissions).

## Alembic

- `alembic upgrade head` — apply all migrations (creates tables, then seeds the 11
  permissions from `../specs/00-architecture-and-standards.md` §5.1).
- `alembic revision --autogenerate -m "message"` — generate a new migration from model
  changes. `alembic/env.py` is async-compatible (uses `async_engine_from_config` +
  `run_sync`) and reads `DATABASE_URL` from `app.core.config.Settings`, so there's a single
  source of truth for the connection string between the app and migrations.

## Known deviations / stubs from the spec (see also the final build report)

- **`PasswordResetToken` table** — not in `backend.md`'s literal 9-table list, but required
  to implement the `/auth/forgot-password` + `/auth/reset-password` routes that same doc
  specifies. Minimal table: `id, user_id, token_hash (sha256), expires_at, used_at,
  created_at`.
- **`RefreshToken.family_id`** — an added column (not in the literal spec table) used to
  implement single-use rotation with reuse-triggers-family-revocation, per `cloud.md`'s
  "theft-detection pattern" description. Tokens issued from the same login chain share a
  `family_id`; reusing an already-rotated token revokes every token sharing that id.
- **`tower_has_active_financials()` stub** (`app/services/tower.py`) — Modules 3/4
  (Maintenance Billing; Special Collections & Expenditure) own the `maintenance_dues` /
  `special_collection_dues` tables this check needs, and neither exists in this codebase yet.
  The function always returns `False` (i.e. `POST /towers/{id}/deactivate` is never blocked
  by this specific check in this codebase), with a `# TODO(module-3/4)` comment describing
  exactly what real query to substitute once those tables land. Everything else about
  deactivate/reactivate (guards, audit logging, superuser-only reactivate) is fully
  implemented — only the missing data dependency is stubbed.

### Module 4 (Special Collections & Expenditure) — scope note

Module 4 has two hard dependencies not yet built in this repo: Module 2 (Flat/Owner/Tenant)
and Module 3 (Maintenance Billing, which owns the shared `payments`/`receipts` tables and the
`record_payment()` service). Only the dependency-free slice is implemented here:

- **Implemented**: `special_collections`/`special_collection_dues`/`expenditures` tables and
  models, all their Pydantic schemas, the equal-split due-generation algorithm (rounding,
  remainder distribution, deterministic `flat_number`-ascending ordering, `NO_ACTIVE_OWNER`
  skip handling — see `app/services/special_collection.py`, unit-tested directly in
  `tests/unit/test_special_collection_split.py`), and: `POST/GET /special-collections`,
  `GET/DELETE /special-collections/{id}`, `GET /special-collections/{id}/dues[/{due_id}]`,
  and the full expenditures CRUD + `POST .../expenditures/attachment-upload-url` +
  `GET .../expenditures/{id}/attachment` (pre-signed S3 URLs via `app/services/storage.py`,
  boto3, tested against `moto` in `tests/integration/test_expenditures.py`).
- **Not implemented (intentionally omitted, not stubbed)**:
  `POST .../dues/{due_id}/mark-paid` and `GET .../dues/{due_id}/receipt` — both hard-depend
  on Module 3's `record_payment()` service, which doesn't exist yet. These routes are simply
  absent from the router rather than stubbed with a 501/TODO endpoint. Backend.md test plan
  items 6-8 (mark-paid delegation, receipt owner-name, grace-period/overdue transition) and
  13 (>300-flat async SQS path) are correspondingly not covered — 13 also needs the
  `special-collection-jobs` SQS worker described in `cloud.md`, not built here.
- **Module 2 workaround**: `special_collection_dues.flat_id`/`.owner_id` are plain
  `UUID NOT NULL` columns with **no DB-level foreign key** to `flats`/`owners` (Module 2
  doesn't exist), mirroring the FK-less `due_type`/`due_id` discriminator pattern the spec
  itself uses for the Module 3 integration. The equal-split algorithm's Module-2 data
  dependency is behind a `FlatDirectory` protocol seam (`app/services/flat_directory.py`);
  the only concrete implementation today is `Module2NotIntegratedFlatDirectory`, which raises
  `501 FLAT_DIRECTORY_NOT_AVAILABLE` rather than fabricating flat data — tests supply a
  `FakeFlatDirectory` (`tests/factories.py`) via `app.dependency_overrides`, the same pattern
  already used for `get_db`. Swapping in real Module 2 queries later is a one-file change
  (replace what `get_flat_directory()` returns).
  - As a further consequence of Module 2 not existing, `SpecialCollectionDueOut`'s
    `flat_number`/`owner_name` (spec: "joined from Module 2 Flat/Owner for display") are
    instead snapshotted onto `special_collection_dues` at generation time, sourced from the
    `FlatDirectory` seam — a deliberate, documented addition beyond the literal spec table
    (see `app/models/special_collection_due.py`).
- **`created_by`/`recorded_by` FK to `association_members`**: both tables' spec columns are
  `NOT NULL` FKs to `association_members.id`. A superuser bypasses tower RBAC entirely
  (`require_permission` returns `None` for them) and normally has no membership row for a
  given tower, so `app/api/deps.py`'s `require_permission_with_member_id()` — an additive
  wrapper around `require_permission()` — resolves a real membership if one exists or raises
  `403 ASSOCIATION_MEMBERSHIP_REQUIRED` rather than writing a nonsensical value.
- **>300-flat sync/async threshold**: the router always takes the synchronous path
  regardless of active-flat count; `SYNC_DUE_GENERATION_FLAT_THRESHOLD` in
  `app/services/special_collection.py` documents where the enqueue-to-SQS branch would go.
  `compute_equal_split`/`generate_dues` are written so an async worker could call the exact
  same functions later — only the router's branch needs to change.
- **S3 integration is new in this codebase** (Module 1 had no file storage yet) — added
  `boto3` as a runtime dependency and `moto[s3]`/`requests` as dev/test-only dependencies,
  plus `S3_BUCKET_NAME`/`AWS_REGION`/`S3_ENDPOINT_URL` settings in `app/core/config.py`
  (the last one is test/local-only, for pointing at moto/localstack).
