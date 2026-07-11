"""Outstanding Dues Report — backend.md §2.2, overview.md acceptance criterion 2 and edge case
"grace period has just changed", backend test plan's exact days_overdue worked example."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from tests.factories import (
    DEFAULT_PASSWORD,
    make_association_member,
    make_billing_cycle,
    make_complex,
    make_flat,
    make_maintenance_due,
    make_maintenance_formula,
    make_primary_owner_for_flat,
    make_role,
    make_tower,
    make_user,
)


async def _login(client, email, password=DEFAULT_PASSWORD):
    return await client.post("/api/v1/auth/login", json={"email": email, "password": password})


async def _setup_reports_admin(db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    role = await make_role(
        db_session, tower_id=tower.id, permission_codes=["VIEW_REPORTS", "VIEW_TOWER_DATA"]
    )
    user = await make_user(db_session, email=f"reports-admin-{uuid4()}@example.com")
    member = await make_association_member(
        db_session, tower_id=tower.id, user_id=user.id, role_id=role.id
    )
    await db_session.commit()
    return tower, user, member


@pytest.mark.asyncio
async def test_outstanding_dues_days_overdue_worked_example(client, db_session):
    """due_date=2026-06-01, grace_period_days=5, as_of=2026-06-10 => days_overdue = 4
    (10 - (1+5))."""
    tower, user, member = await _setup_reports_admin(db_session)
    formula = await make_maintenance_formula(db_session, tower_id=tower.id, created_by=member.id)
    cycle = await make_billing_cycle(
        db_session, tower_id=tower.id, formula_id=formula.id, created_by=member.id,
        month=6, year=2026, due_date=date(2026, 6, 1), grace_period_days_snapshot=5,
    )
    flat = await make_flat(db_session, tower_id=tower.id, flat_number="201")
    owner = await make_primary_owner_for_flat(
        db_session, flat_id=flat.id, created_by_user_id=user.id, full_name="Kiran Patel"
    )
    await make_maintenance_due(
        db_session, billing_cycle_id=cycle.id, tower_id=tower.id, flat_id=flat.id,
        primary_owner_id=owner.id, due_date=date(2026, 6, 1), status="overdue",
        amount=Decimal("3000.00"),
    )
    await db_session.commit()

    await _login(client, user.email)
    resp = await client.get(
        f"/api/v1/towers/{tower.id}/reports/outstanding-dues",
        params={"as_of_date": "2026-06-10"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1
    row = body["items"][0]
    assert row["grace_period_days"] == 5
    assert row["days_overdue"] == 4
    assert row["due_type"] == "maintenance"


@pytest.mark.asyncio
async def test_outstanding_dues_excludes_pending_dues(client, db_session):
    tower, user, member = await _setup_reports_admin(db_session)
    formula = await make_maintenance_formula(db_session, tower_id=tower.id, created_by=member.id)
    cycle = await make_billing_cycle(
        db_session, tower_id=tower.id, formula_id=formula.id, created_by=member.id
    )
    flat = await make_flat(db_session, tower_id=tower.id, flat_number="301")
    owner = await make_primary_owner_for_flat(
        db_session, flat_id=flat.id, created_by_user_id=user.id
    )
    await make_maintenance_due(
        db_session, billing_cycle_id=cycle.id, tower_id=tower.id, flat_id=flat.id,
        primary_owner_id=owner.id, status="pending",
    )
    await db_session.commit()

    await _login(client, user.email)
    resp = await client.get(f"/api/v1/towers/{tower.id}/reports/outstanding-dues")
    assert resp.status_code == 200
    assert resp.json()["items"] == []


@pytest.mark.asyncio
async def test_outstanding_dues_uses_grace_period_snapshot_not_current_config(client, db_session):
    """overview.md edge case: grace period changes apply to future cycles only — an existing
    due's days_overdue must use the grace period value stored on its billing cycle at
    generation time, unaffected by a later change to the tower's current grace period config."""
    tower, user, member = await _setup_reports_admin(db_session)
    formula = await make_maintenance_formula(db_session, tower_id=tower.id, created_by=member.id)
    cycle = await make_billing_cycle(
        db_session, tower_id=tower.id, formula_id=formula.id, created_by=member.id,
        month=6, year=2026, due_date=date(2026, 6, 1), grace_period_days_snapshot=5,
    )
    flat = await make_flat(db_session, tower_id=tower.id, flat_number="401")
    owner = await make_primary_owner_for_flat(
        db_session, flat_id=flat.id, created_by_user_id=user.id
    )
    await make_maintenance_due(
        db_session, billing_cycle_id=cycle.id, tower_id=tower.id, flat_id=flat.id,
        primary_owner_id=owner.id, due_date=date(2026, 6, 1), status="overdue",
    )
    await db_session.commit()

    # Simulate the tower's *current* grace period config changing after generation — the
    # report must ignore this and keep using the cycle's own snapshot.
    from tests.factories import make_grace_period_config

    await make_grace_period_config(
        db_session, tower_id=tower.id, created_by=member.id, grace_period_days=30,
        effective_from=date(2026, 7, 1),
    )
    await db_session.commit()

    await _login(client, user.email)
    resp = await client.get(
        f"/api/v1/towers/{tower.id}/reports/outstanding-dues",
        params={"as_of_date": "2026-06-10"},
    )
    body = resp.json()
    assert body["items"][0]["grace_period_days"] == 5
    assert body["items"][0]["days_overdue"] == 4


@pytest.mark.asyncio
async def test_outstanding_dues_includes_overdue_special_collection_due(client, db_session):
    """Special-collection dues have no grace-period concept in Module 4's model — this build's
    documented decision is `grace_period_days=0` for that source, so days_overdue is simply
    `as_of_date - due_date`."""
    from app.models.special_collection_due import SpecialCollectionDue
    from tests.factories import make_special_collection

    tower, user, member = await _setup_reports_admin(db_session)
    collection = await make_special_collection(db_session, tower_id=tower.id, created_by=member.id)
    sc_due = SpecialCollectionDue(
        special_collection_id=collection.id,
        tower_id=tower.id,
        flat_id=uuid4(),
        flat_number="501",
        owner_id=uuid4(),
        owner_name="Farida Khan",
        amount=Decimal("5000.00"),
        due_date=date(2026, 6, 1),
        status="overdue",
    )
    db_session.add(sc_due)
    await db_session.commit()

    await _login(client, user.email)
    resp = await client.get(
        f"/api/v1/towers/{tower.id}/reports/outstanding-dues",
        params={"as_of_date": "2026-06-11"},
    )
    body = resp.json()
    assert len(body["items"]) == 1
    row = body["items"][0]
    assert row["due_type"] == "special_collection"
    assert row["grace_period_days"] == 0
    assert row["days_overdue"] == 10
    assert row["owner_names"] == ["Farida Khan"]
