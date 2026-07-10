"""backend.md §8.2 — `mark-paid` / `record_payment()` integration tests. See
`test_billing_cycle_generation.py`'s module docstring for why these aren't runnable in this
sandbox (no Docker) and what fixture pattern they follow.
"""

import pytest
from sqlalchemy import select

from app.models.maintenance_due import MaintenanceDue
from app.models.payment import Payment
from app.models.receipt import Receipt
from tests.factories import (
    DEFAULT_PASSWORD,
    make_billing_admin,
    make_billing_cycle,
    make_complex,
    make_flat,
    make_maintenance_formula,
    make_owner,
    make_tenant,
    make_tower,
)


async def _login(client, email, password=DEFAULT_PASSWORD):
    return await client.post("/api/v1/auth/login", json={"email": email, "password": password})


async def _setup_paid_ready_due(db_session, *, assigned_to_type="owner"):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    member = await make_billing_admin(
        db_session, tower_id=tower.id, email="payer-admin@example.com"
    )
    formula = await make_maintenance_formula(db_session, tower_id=tower.id, created_by=member.id)

    flat = await make_flat(
        db_session,
        tower_id=tower.id,
        occupancy_status="tenant_occupied" if assigned_to_type == "tenant" else "owner_occupied",
    )
    owner = await make_owner(db_session, flat_id=flat.id, full_name="Asha Rao")
    tenant = None
    if assigned_to_type == "tenant":
        tenant = await make_tenant(db_session, flat_id=flat.id, full_name="Ravi Kumar")

    cycle = await make_billing_cycle(
        db_session, tower_id=tower.id, formula_id=formula.id, created_by=member.id
    )

    due = MaintenanceDue(
        billing_cycle_id=cycle.id,
        tower_id=tower.id,
        flat_id=flat.id,
        amount=2000,
        carpet_area_snapshot=flat.carpet_area,
        assigned_to_type=assigned_to_type,
        assigned_to_id=tenant.id if tenant is not None else owner.id,
        assigned_to_name_snapshot=tenant.full_name if tenant is not None else owner.full_name,
        primary_owner_id_snapshot=owner.id,
        due_date=cycle.due_date,
        status="pending",
    )
    db_session.add(due)
    await db_session.flush()
    await db_session.commit()
    return tower, due


@pytest.mark.asyncio
async def test_mark_paid_creates_payment_and_receipt_and_flips_due_to_paid(client, db_session):
    tower, due = await _setup_paid_ready_due(db_session)
    await _login(client, "payer-admin@example.com")

    resp = await client.patch(
        f"/api/v1/towers/{tower.id}/dues/{due.id}/mark-paid",
        json={
            "payment_date": "2026-07-09",
            "amount_received": 2000.00,
            "payment_mode": "cash",
            "reference_number": None,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["due"]["status"] == "paid"
    assert body["receipt"]["receipt_number"]
    assert body["receipt"]["download_url"]

    await db_session.refresh(due)
    assert due.status == "paid"

    payment = await db_session.scalar(select(Payment).where(Payment.due_id == due.id))
    assert payment is not None
    assert payment.amount_received == 2000

    receipt = await db_session.scalar(select(Receipt).where(Receipt.due_id == due.id))
    assert receipt is not None
    assert receipt.owner_name_snapshot == "Asha Rao"


@pytest.mark.asyncio
async def test_mark_paid_twice_returns_409_and_creates_no_duplicate_rows(client, db_session):
    tower, due = await _setup_paid_ready_due(db_session)
    await _login(client, "payer-admin@example.com")

    payload = {
        "payment_date": "2026-07-09",
        "amount_received": 2000.00,
        "payment_mode": "cash",
        "reference_number": None,
    }
    first = await client.patch(f"/api/v1/towers/{tower.id}/dues/{due.id}/mark-paid", json=payload)
    assert first.status_code == 200

    second = await client.patch(f"/api/v1/towers/{tower.id}/dues/{due.id}/mark-paid", json=payload)
    assert second.status_code == 409
    assert second.json()["error_code"] == "DUE_ALREADY_PAID"

    payments = (
        (await db_session.execute(select(Payment).where(Payment.due_id == due.id))).scalars().all()
    )
    receipts = (
        (await db_session.execute(select(Receipt).where(Receipt.due_id == due.id))).scalars().all()
    )
    assert len(payments) == 1
    assert len(receipts) == 1


@pytest.mark.asyncio
async def test_mark_paid_with_non_positive_amount_returns_422_and_creates_nothing(
    client, db_session
):
    tower, due = await _setup_paid_ready_due(db_session)
    await _login(client, "payer-admin@example.com")

    resp = await client.patch(
        f"/api/v1/towers/{tower.id}/dues/{due.id}/mark-paid",
        json={
            "payment_date": "2026-07-09",
            "amount_received": 0,
            "payment_mode": "cash",
            "reference_number": None,
        },
    )
    assert resp.status_code == 422
    assert resp.json()["error_code"] == "VALIDATION_ERROR"
    assert "amount_received" in resp.json()["field_errors"]

    count = await db_session.scalar(select(Payment).where(Payment.due_id == due.id))
    assert count is None


@pytest.mark.asyncio
async def test_receipt_names_primary_owner_even_when_tenant_is_the_assignee(client, db_session):
    """overview.md edge case 4 / acceptance criterion 12."""
    tower, due = await _setup_paid_ready_due(db_session, assigned_to_type="tenant")
    assert due.assigned_to_name_snapshot == "Ravi Kumar"

    await _login(client, "payer-admin@example.com")
    resp = await client.patch(
        f"/api/v1/towers/{tower.id}/dues/{due.id}/mark-paid",
        json={
            "payment_date": "2026-07-09",
            "amount_received": 2000.00,
            "payment_mode": "bank_transfer",
            "reference_number": "REF123",
        },
    )
    assert resp.status_code == 200

    receipt = await db_session.scalar(select(Receipt).where(Receipt.due_id == due.id))
    assert receipt.owner_name_snapshot == "Asha Rao"
    assert "Ravi Kumar" not in receipt.owner_name_snapshot


@pytest.mark.asyncio
async def test_cross_tower_due_access_is_denied_not_leaked(client, db_session):
    tower_a, due_a = await _setup_paid_ready_due(db_session)
    complex_row = await make_complex(db_session)
    tower_b = await make_tower(db_session, complex_id=complex_row.id, name="Tower B", code="TWB")
    await make_billing_admin(db_session, tower_id=tower_b.id, email="tower-b-admin@example.com")
    await db_session.commit()

    await _login(client, "tower-b-admin@example.com")
    resp = await client.get(f"/api/v1/towers/{tower_b.id}/dues/{due_a.id}")
    assert resp.status_code == 404  # scoped lookup: not found in *this* tower, no leak

    resp2 = await client.get(f"/api/v1/towers/{tower_a.id}/dues/{due_a.id}")
    assert resp2.status_code == 403  # not even a member of tower A
