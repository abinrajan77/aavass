"""Monthly Collection Report — backend.md §2.1, overview.md acceptance criterion 1, backend
test plan: "total_paid matches the sum of Payment.amount_received for that billing_cycle_id
queried directly against Module 3's tables"."""

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.models.maintenance_due import MaintenanceDue
from app.models.payment import Payment
from app.services.payments import record_payment
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
    make_tenant,
    make_tower,
    make_user,
)


async def _login(client, email, password=DEFAULT_PASSWORD):
    return await client.post("/api/v1/auth/login", json={"email": email, "password": password})


async def _setup_reports_admin(db_session, *, permission_codes=None):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    role = await make_role(
        db_session,
        tower_id=tower.id,
        permission_codes=permission_codes or ["VIEW_REPORTS", "VIEW_TOWER_DATA"],
    )
    user = await make_user(db_session, email=f"reports-admin-{uuid4()}@example.com")
    member = await make_association_member(
        db_session, tower_id=tower.id, user_id=user.id, role_id=role.id
    )
    await db_session.commit()
    return tower, user, member


@pytest.mark.asyncio
async def test_collection_report_lists_mixed_status_dues_and_reconciles_totals(
    client, db_session
):
    tower, user, member = await _setup_reports_admin(db_session)
    formula = await make_maintenance_formula(db_session, tower_id=tower.id, created_by=member.id)
    cycle = await make_billing_cycle(
        db_session, tower_id=tower.id, formula_id=formula.id, created_by=member.id
    )

    # Flat 1: owner-occupied, paid.
    flat1 = await make_flat(
        db_session, tower_id=tower.id, flat_number="101", occupancy_status="owner_occupied"
    )
    owner1 = await make_primary_owner_for_flat(
        db_session, flat_id=flat1.id, created_by_user_id=user.id, full_name="Asha Rao"
    )
    due1 = await make_maintenance_due(
        db_session, billing_cycle_id=cycle.id, tower_id=tower.id, flat_id=flat1.id,
        primary_owner_id=owner1.id, assigned_to_type="owner", assigned_to_id=owner1.id,
        assigned_to_name_snapshot=owner1.full_name, amount=Decimal("2500.00"),
    )

    # Flat 2: tenant-occupied, pending.
    flat2 = await make_flat(
        db_session, tower_id=tower.id, flat_number="102", occupancy_status="tenant_occupied"
    )
    owner2 = await make_primary_owner_for_flat(
        db_session, flat_id=flat2.id, created_by_user_id=user.id, full_name="Vikram Singh"
    )
    tenant2 = await make_tenant(db_session, flat_id=flat2.id, full_name="Rohit Sharma")
    await make_maintenance_due(
        db_session, billing_cycle_id=cycle.id, tower_id=tower.id, flat_id=flat2.id,
        primary_owner_id=owner2.id, assigned_to_type="tenant", assigned_to_id=tenant2.id,
        assigned_to_name_snapshot=tenant2.full_name, amount=Decimal("1800.00"), status="pending",
    )

    # Flat 3: owner-occupied, overdue.
    flat3 = await make_flat(
        db_session, tower_id=tower.id, flat_number="103", occupancy_status="owner_occupied"
    )
    owner3 = await make_primary_owner_for_flat(
        db_session, flat_id=flat3.id, created_by_user_id=user.id, full_name="Meena Iyer"
    )
    await make_maintenance_due(
        db_session, billing_cycle_id=cycle.id, tower_id=tower.id, flat_id=flat3.id,
        primary_owner_id=owner3.id, assigned_to_type="owner", assigned_to_id=owner3.id,
        assigned_to_name_snapshot=owner3.full_name, amount=Decimal("2200.00"), status="overdue",
    )
    await db_session.commit()

    receipt = await record_payment(
        db_session, tower_id=tower.id, due_type="maintenance", due_id=due1.id,
        payment_date=cycle.due_date, amount_received=Decimal("2500.00"), payment_mode="cash",
        reference_number=None, recorded_by=member,
    )

    await _login(client, user.email)
    resp = await client.get(
        f"/api/v1/towers/{tower.id}/reports/collection",
        params={"billing_cycle_id": str(cycle.id)},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 3
    assert body["billing_month"] == cycle.month
    assert body["billing_year"] == cycle.year

    by_flat = {row["flat_number"]: row for row in body["items"]}
    assert by_flat["101"]["status"] == "paid"
    assert by_flat["101"]["receipt_number"] == receipt.receipt_number
    assert by_flat["101"]["owner_names"] == ["Asha Rao"]
    assert by_flat["102"]["status"] == "pending"
    assert by_flat["102"]["resident_type"] == "tenant"
    assert by_flat["102"]["resident_name"] == "Rohit Sharma"
    assert by_flat["103"]["status"] == "overdue"

    # Acceptance criterion 1: sum of "paid" amounts equals sum of Payment.amount_received for
    # that cycle, queried directly against Module 3's own table.
    expected_total_paid = await db_session.scalar(
        select(func.coalesce(func.sum(Payment.amount_received), 0)).where(
            Payment.due_type == "maintenance",
            Payment.due_id.in_(
                select(MaintenanceDue.id).where(MaintenanceDue.billing_cycle_id == cycle.id)
            ),
        )
    )
    assert Decimal(body["totals"]["total_paid"]) == Decimal(expected_total_paid)
    assert Decimal(body["totals"]["total_pending"]) == Decimal("1800.00")
    assert Decimal(body["totals"]["total_overdue"]) == Decimal("2200.00")
    assert Decimal(body["totals"]["total_due"]) == Decimal("6500.00")


@pytest.mark.asyncio
async def test_collection_report_empty_cycle_returns_200_with_empty_items(client, db_session):
    """overview.md edge case: a billing cycle with no dues yet is a valid empty state, not an
    error — 200 with empty items/zeroed totals."""
    tower, user, member = await _setup_reports_admin(db_session)
    formula = await make_maintenance_formula(db_session, tower_id=tower.id, created_by=member.id)
    cycle = await make_billing_cycle(
        db_session, tower_id=tower.id, formula_id=formula.id, created_by=member.id,
        status="generating",
    )
    await db_session.commit()

    await _login(client, user.email)
    resp = await client.get(
        f"/api/v1/towers/{tower.id}/reports/collection",
        params={"billing_cycle_id": str(cycle.id)},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert Decimal(body["totals"]["total_due"]) == Decimal("0.00")


@pytest.mark.asyncio
async def test_collection_report_requires_view_reports_permission(client, db_session):
    tower, user, _member = await _setup_reports_admin(
        db_session, permission_codes=["VIEW_TOWER_DATA"]
    )
    await db_session.commit()
    await _login(client, user.email)
    resp = await client.get(
        f"/api/v1/towers/{tower.id}/reports/collection",
        params={"billing_cycle_id": str(uuid4())},
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "PERMISSION_DENIED"


@pytest.mark.asyncio
async def test_collection_report_unknown_cycle_returns_404(client, db_session):
    tower, user, _member = await _setup_reports_admin(db_session)
    await db_session.commit()
    await _login(client, user.email)
    resp = await client.get(
        f"/api/v1/towers/{tower.id}/reports/collection",
        params={"billing_cycle_id": str(uuid4())},
    )
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "BILLING_CYCLE_NOT_FOUND"
