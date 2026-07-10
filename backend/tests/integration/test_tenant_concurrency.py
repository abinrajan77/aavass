"""Concurrency test for `app/services/occupancy.py::create_tenant` —
`specs/02-flat-owner-tenant/backend.md`: "two simultaneous POST .../tenants requests against
the same flat ... result in exactly one success and one 409 — proves the row lock actually
serializes the race, not just the happy-path pre-check."

This deliberately does NOT reuse the suite's standard `client`/`db_session` fixtures: those
give every request in a test the *same* `AsyncSession` (one SAVEPOINT-per-test rollback, per
`conftest.py`'s docstring) so the whole suite can roll back cleanly without touching the real
DB. Two coroutines sharing one `AsyncSession` cannot exhibit real cross-transaction row-lock
contention — SQLAlchemy's `AsyncSession` isn't safe for concurrent use from two tasks, and even
if it were, both statements would run against the same open transaction rather than two
genuinely separate ones. Proving the `SELECT ... FOR UPDATE` lock requires two independent
connections that can actually block on each other, so this test opens two of its own sessions
against the same test-container database (via the session-scoped `database_url` fixture) and
commits for real, cleaning up isn't needed since each test run gets its own disposable
Postgres container.
"""

import asyncio
from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.errors import AppError
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.tenant import TenantCreate
from app.services import occupancy
from tests.factories import make_complex, make_flat, make_tower, make_user


@pytest.mark.asyncio
async def test_concurrent_tenant_creation_yields_one_success_and_one_conflict(database_url):
    engine = create_async_engine(database_url, future=True)
    session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)

    async with session_maker() as setup_session:
        complex_row = await make_complex(setup_session, name="Concurrency Complex")
        tower = await make_tower(
            setup_session, complex_id=complex_row.id, name="ConcTower", code="CNC"
        )
        flat = await make_flat(setup_session, tower_id=tower.id, flat_number="CNC-1")
        actor = await make_user(setup_session, email="concurrency-actor@example.com")
        await setup_session.commit()
        flat_id, actor_id = flat.id, actor.id

    async def _attempt(full_name: str, phone: str) -> str:
        async with session_maker() as session:
            actor_row = await session.get(User, actor_id)
            assert actor_row is not None
            try:
                await occupancy.create_tenant(
                    session,
                    flat_id=flat_id,
                    payload=TenantCreate(
                        full_name=full_name, phone=phone, lease_start=date(2024, 1, 1)
                    ),
                    actor=actor_row,
                )
                await session.commit()
                return "success"
            except AppError as exc:
                await session.rollback()
                return exc.error_code

    results = await asyncio.gather(
        _attempt("Racer A", "9111100001"), _attempt("Racer B", "9111100002")
    )
    assert sorted(results) == ["ONE_ACTIVE_TENANT", "success"]

    async with session_maker() as verify_session:
        active_count = await verify_session.scalar(
            select(func.count()).select_from(Tenant).where(
                Tenant.flat_id == flat_id, Tenant.is_active.is_(True)
            )
        )
        assert active_count == 1

    await engine.dispose()
