"""Test fixtures.

Primary path: spin up a real Postgres via `testcontainers-python` (Docker-in-Docker works in
this sandbox — verified with a plain `docker ps` before building this suite). Every test in
this suite exercises the actual asyncpg driver, real constraints (unique/foreign key), and
Postgres-specific features (`gen_random_uuid()`, JSONB) — nothing here mocks the DB.

Fallback (documented in README.md): if a future environment has no Docker access at all,
point `DATABASE_URL` at the docker-compose Postgres service instead (`docker-compose up -d`
then run `pytest` with `DATABASE_URL=postgresql+asyncpg://aavaas:aavaas@localhost:5432/aavaas_test`)
and skip the testcontainers fixture. This repo does not implement that fallback path in code
since testcontainers works in this environment; it is a documented manual alternative only.

Event-loop note: schema creation runs once per session on its own throwaway `asyncio.run()`
loop (a plain sync fixture, not a pytest-asyncio fixture) so it never shares an event loop
with any test. The per-test `engine`/`db_session` fixtures are function-scoped, matching
pytest-asyncio's default per-test loop scope — asyncpg connections are loop-bound, so
reusing a connection created on one loop from a test running on a different loop raises
"Future attached to a different loop" (this bit us during initial setup with a
session-scoped async engine; keeping engine/session function-scoped avoids it entirely).
"""

import asyncio
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from app.core.permissions import PERMISSION_CATALOG
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.permission import Permission


@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:16", driver="asyncpg") as container:
        yield container


async def _create_schema_and_seed(async_url: str) -> None:
    eng = create_async_engine(async_url, future=True)
    async with eng.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
        await conn.run_sync(Base.metadata.create_all)
        for code, description in PERMISSION_CATALOG:
            await conn.execute(
                Permission.__table__.insert().values(
                    id=uuid.uuid4(), code=code, description=description
                )
            )
    await eng.dispose()


@pytest.fixture(scope="session")
def database_url(postgres_container) -> str:
    """Runs schema creation + permission seeding exactly once per test session, on its own
    throwaway event loop (plain `asyncio.run`, no pytest-asyncio involvement)."""
    raw_url = postgres_container.get_connection_url()  # postgresql+psycopg2://...
    async_url = raw_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
    asyncio.run(_create_schema_and_seed(async_url))
    return async_url


@pytest_asyncio.fixture
async def engine(database_url) -> AsyncIterator:
    eng = create_async_engine(database_url, future=True)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine) -> AsyncIterator[AsyncSession]:
    """One test = one outer transaction, rolled back at the end for isolation, with a SAVEPOINT
    so code under test can freely call `db.commit()` without actually persisting across tests.

    This is SQLAlchemy's documented pattern for "joining a session into an external
    transaction" adapted for asyncio: the outer transaction is never committed (only rolled
    back at teardown), and a nested SAVEPOINT is transparently restarted every time the
    application code's `session.commit()` ends it, so `write_audit_log()`'s atomicity
    (audit row + entity row in the same commit) is exercised exactly as it runs in prod.
    """
    connection = await engine.connect()
    outer_trans = await connection.begin()

    session_maker = async_sessionmaker(bind=connection, expire_on_commit=False, class_=AsyncSession)
    session = session_maker()

    await connection.begin_nested()

    @event.listens_for(session.sync_session, "after_transaction_end")
    def _restart_savepoint(sync_session, transaction):
        if connection.closed:
            return
        if not connection.sync_connection.in_nested_transaction():
            connection.sync_connection.begin_nested()

    try:
        yield session
    finally:
        await session.close()
        if outer_trans.is_active:
            await outer_trans.rollback()
        await connection.close()


@pytest_asyncio.fixture
async def client(db_session) -> AsyncIterator[AsyncClient]:
    async def _get_db_override():
        yield db_session

    app.dependency_overrides[get_db] = _get_db_override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)
