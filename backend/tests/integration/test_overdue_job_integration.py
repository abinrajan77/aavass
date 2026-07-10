"""backend.md §8.2 — the nightly overdue-transition job (`app.services.overdue`), exercised
against a real DB so the `billing_cycles` join and `audit_log` write are real. See
`test_billing_cycle_generation.py`'s module docstring re: sandbox runnability."""

from datetime import date

import pytest
from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.maintenance_due import MaintenanceDue
from app.services.overdue import SYSTEM_ACTOR_LABEL, run_overdue_transition
from tests.factories import (
    make_billing_cycle,
    make_complex,
    make_flat,
    make_maintenance_formula,
    make_owner,
    make_tower,
    make_user,
)


async def _make_pending_due(db_session, *, tower, formula, grace_period_days, due_date):
    user = await make_user(db_session, email=f"creator-{due_date.isoformat()}@example.com")
    flat = await make_flat(db_session, tower_id=tower.id)
    owner = await make_owner(db_session, flat_id=flat.id)
    cycle = await make_billing_cycle(
        db_session,
        tower_id=tower.id,
        formula_id=formula.id,
        created_by=user.id,
        due_date=due_date,
        grace_period_days_snapshot=grace_period_days,
        month=due_date.month,
        year=due_date.year,
    )
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
        due_date=due_date,
        status="pending",
    )
    db_session.add(due)
    await db_session.flush()
    return due


@pytest.mark.asyncio
async def test_flips_pending_past_grace_to_overdue_and_writes_audit_log(db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    user = await make_user(db_session, email="formula-owner@example.com")
    formula = await make_maintenance_formula(db_session, tower_id=tower.id, created_by=user.id)

    overdue_due = await _make_pending_due(
        db_session, tower=tower, formula=formula, grace_period_days=0, due_date=date(2026, 7, 10)
    )
    still_pending_due = await _make_pending_due(
        db_session, tower=tower, formula=formula, grace_period_days=5, due_date=date(2026, 7, 10)
    )
    await db_session.commit()

    flipped = await run_overdue_transition(db_session, as_of=date(2026, 7, 11))

    assert overdue_due.id in flipped
    assert still_pending_due.id not in flipped

    await db_session.refresh(overdue_due)
    await db_session.refresh(still_pending_due)
    assert overdue_due.status == "overdue"
    assert still_pending_due.status == "pending"

    entry = await db_session.scalar(
        select(AuditLog).where(
            AuditLog.action == "due_overdue_transition", AuditLog.entity_id == overdue_due.id
        )
    )
    assert entry is not None
    assert entry.user_id is None  # system-generated
    assert entry.actor_label == SYSTEM_ACTOR_LABEL


@pytest.mark.asyncio
async def test_running_the_job_twice_in_a_day_does_not_double_flip_or_double_log(db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    user = await make_user(db_session, email="idempotent-owner@example.com")
    formula = await make_maintenance_formula(db_session, tower_id=tower.id, created_by=user.id)

    due = await _make_pending_due(
        db_session, tower=tower, formula=formula, grace_period_days=0, due_date=date(2026, 7, 10)
    )
    await db_session.commit()

    await run_overdue_transition(db_session, as_of=date(2026, 7, 11))
    await run_overdue_transition(db_session, as_of=date(2026, 7, 11))

    await db_session.refresh(due)
    assert due.status == "overdue"

    entries = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "due_overdue_transition", AuditLog.entity_id == due.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(entries) == 1  # not double-logged on the second run


@pytest.mark.asyncio
async def test_marking_paid_after_overdue_flip_is_still_allowed(db_session):
    """backend.md §3 — 'Marking a due Paid is allowed regardless of whether the nightly job
    has already flipped it to Overdue.'"""
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    user = await make_user(db_session, email="pay-after-overdue@example.com")
    formula = await make_maintenance_formula(db_session, tower_id=tower.id, created_by=user.id)
    due = await _make_pending_due(
        db_session, tower=tower, formula=formula, grace_period_days=0, due_date=date(2026, 7, 10)
    )
    await db_session.commit()

    await run_overdue_transition(db_session, as_of=date(2026, 7, 11))
    await db_session.refresh(due)
    assert due.status == "overdue"

    # record_payment() only rejects status == 'paid', so an Overdue due must still be payable.
    from app.services.payments import record_payment
    from tests.factories import make_association_member, make_role

    role = await make_role(db_session, tower_id=tower.id, permission_codes=["RECORD_PAYMENT"])
    member = await make_association_member(
        db_session, tower_id=tower.id, user_id=user.id, role_id=role.id
    )
    await db_session.commit()

    receipt = await record_payment(
        db_session,
        tower_id=tower.id,
        due_type="maintenance",
        due_id=due.id,
        payment_date=date(2026, 7, 20),
        amount_received=due.amount,
        payment_mode="cash",
        reference_number=None,
        recorded_by=member,
    )
    assert receipt is not None
    await db_session.refresh(due)
    assert due.status == "paid"
