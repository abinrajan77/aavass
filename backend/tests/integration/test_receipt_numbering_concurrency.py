"""backend.md §8.1's receipt-numbering concurrency test: "no gaps under 100 simulated
concurrent `mark-paid` calls against the same tower ... drives the `receipt_counters` row-lock
test, can be simulated with asyncio tasks against a test DB." This needs a real DB (row locks
are meaningless against the savepoint-based `db_session` fixture, which is a single connection)
so it uses the session-scoped `engine` fixture directly with one connection+session per
simulated concurrent request, matching `tests/conftest.py`'s own note that `engine`/`db_session`
are intentionally separated for exactly this kind of multi-connection scenario.

Not runnable in this sandbox (no Docker) — see `test_billing_cycle_generation.py`'s module
docstring.
"""

import asyncio
from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.maintenance_due import MaintenanceDue
from app.models.receipt import Receipt
from app.services.payments import record_payment
from tests.factories import (
    make_association_member,
    make_billing_cycle,
    make_complex,
    make_flat,
    make_maintenance_formula,
    make_owner,
    make_role,
    make_tower,
    make_user,
)

CONCURRENCY = 100


@pytest.mark.asyncio
async def test_receipt_numbers_have_no_gaps_or_collisions_under_concurrent_mark_paid(engine):
    session_maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)

    async with session_maker() as setup_db:
        complex_row = await make_complex(setup_db)
        tower = await make_tower(setup_db, complex_id=complex_row.id, code="CCY")
        user = await make_user(setup_db, email="concurrency-recorder@example.com")
        role = await make_role(setup_db, tower_id=tower.id, permission_codes=["RECORD_PAYMENT"])
        member = await make_association_member(
            setup_db, tower_id=tower.id, user_id=user.id, role_id=role.id
        )
        formula = await make_maintenance_formula(setup_db, tower_id=tower.id, created_by=member.id)

        due_ids = []
        cycle = await make_billing_cycle(
            setup_db, tower_id=tower.id, formula_id=formula.id, created_by=member.id
        )
        for i in range(CONCURRENCY):
            flat = await make_flat(setup_db, tower_id=tower.id, flat_number=str(i))
            owner = await make_owner(setup_db, flat_id=flat.id, full_name=f"Owner {i}")
            due = MaintenanceDue(
                billing_cycle_id=cycle.id,
                tower_id=tower.id,
                flat_id=flat.id,
                amount=2000,
                carpet_area_snapshot=flat.carpet_area,
                assigned_to_type="owner",
                assigned_to_id=owner.id,
                assigned_to_name_snapshot=owner.full_name,
                primary_owner_id_snapshot=owner.id,
                due_date=date(2026, 7, 10),
                status="pending",
            )
            setup_db.add(due)
            await setup_db.flush()
            due_ids.append(due.id)
        await setup_db.commit()
        member_id, tower_id_ = member.id, tower.id

    async def _pay(due_id):
        async with session_maker() as db:
            recorder = await db.get(type(member), member_id)
            await record_payment(
                db,
                tower_id=tower_id_,
                due_type="maintenance",
                due_id=due_id,
                payment_date=date(2026, 7, 15),
                amount_received=2000,
                payment_mode="cash",
                reference_number=None,
                recorded_by=recorder,
            )

    await asyncio.gather(*(_pay(due_id) for due_id in due_ids))

    async with session_maker() as verify_db:
        receipts = (
            (
                await verify_db.execute(
                    select(Receipt)
                    .where(Receipt.tower_id == tower_id_)
                    .order_by(Receipt.receipt_number)
                )
            )
            .scalars()
            .all()
        )
        assert len(receipts) == CONCURRENCY
        numbers = sorted(int(r.receipt_number.split("-")[-1]) for r in receipts)
        assert numbers == list(range(1, CONCURRENCY + 1))  # no gaps, no collisions
