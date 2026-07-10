# Aavaas Backend — Module 1: Auth, RBAC & Tower/Complex Setup

FastAPI (Python 3.12) service implementing Module 1 of the Aavaas spec set: login/JWT auth,
the RBAC engine (permissions/roles/association members), `ApartmentComplex`/`Tower` CRUD,
and the shared `audit_log` write helper other modules import.

See `../specs/01-auth-rbac-tower-setup/` for the full spec (`overview.md`, `backend.md`,
`cloud.md`) this implementation follows.

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
