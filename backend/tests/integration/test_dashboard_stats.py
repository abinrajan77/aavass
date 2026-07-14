"""Integration test for the tower admin dashboard aggregate endpoint
(app/services/dashboard.py) — reconciles against Modules 3/4's own source-of-truth tables,
mirroring the "must never introduce a parallel/cached snapshot" rule from
specs/05-reporting-owner-portal-notifications/backend.md, which applies equally here."""

from datetime import date
from decimal import Decimal

import pytest

from app.models.maintenance_due import MaintenanceDue
from tests.factories import (
    DEFAULT_PASSWORD,
    make_billing_admin,
    make_billing_cycle,
    make_complex,
    make_expenditure,
    make_flat,
    make_maintenance_formula,
    make_primary_owner_for_flat,
    make_special_collection,
    make_tower,
)


async def _login(client, email, password=DEFAULT_PASSWORD):
    return await client.post("/api/v1/auth/login", json={"email": email, "password": password})


@pytest.mark.asyncio
async def test_dashboard_stats_reconcile_across_modules(client, db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    member = await make_billing_admin(
        db_session,
        tower_id=tower.id,
        email="dash-admin@example.com",
        permission_codes=[
            "VIEW_TOWER_DATA", "CONFIGURE_BILLING", "CREATE_BILLING_CYCLE", "RECORD_PAYMENT",
        ],
    )

    occupied_flat = await make_flat(db_session, tower_id=tower.id, flat_number="101",
                                     occupancy_status="owner_occupied")
    owner = await make_primary_owner_for_flat(
        db_session, flat_id=occupied_flat.id, created_by_user_id=member.user_id
    )
    await make_flat(db_session, tower_id=tower.id, flat_number="102", occupancy_status="vacant")
    await db_session.commit()

    formula = await make_maintenance_formula(
        db_session, tower_id=tower.id, created_by=member.id, base_amount=2000, per_sqft_rate=2
    )
    today = date.today()
    cycle = await make_billing_cycle(
        db_session, tower_id=tower.id, formula_id=formula.id, created_by=member.id,
        month=today.month, year=today.year, due_date=today, grace_period_days_snapshot=5,
    )
    due = MaintenanceDue(
        billing_cycle_id=cycle.id, tower_id=tower.id, flat_id=occupied_flat.id,
        amount=Decimal("3000.00"), carpet_area_snapshot=Decimal("850.00"),
        assigned_to_type="owner", assigned_to_id=owner.id,
        assigned_to_name_snapshot="Asha Rao", primary_owner_id_snapshot=owner.id,
        due_date=today, status="overdue",
    )
    db_session.add(due)
    await make_expenditure(
        db_session, tower_id=tower.id, recorded_by=member.id,
        expenditure_date=today, amount=Decimal("1500.00"),
    )
    collection = await make_special_collection(
        db_session, tower_id=tower.id, created_by=member.id, total_amount=Decimal("5000.00"),
    )
    await db_session.commit()

    await _login(client, "dash-admin@example.com")
    resp = await client.get(f"/api/v1/towers/{tower.id}/dashboard-stats")
    assert resp.status_code == 200
    body = resp.json()

    assert body["total_flats"] == 2
    assert body["occupied_flats"] == 1
    assert body["vacant_flats"] == 1
    assert body["overdue_dues_count"] == 1
    assert Decimal(body["overdue_amount"]) == Decimal("3000.00")
    assert float(body["expenditure_this_month"]) == 1500.00
    # `make_special_collection` is the bare-row factory (no dues generated) — a collection with
    # zero due rows never appears in the "open" count, matching the special-collections list
    # endpoint's own `status=open` definition (>=1 non-paid due), which this dashboard mirrors.
    assert collection is not None
    assert body["open_special_collections_count"] == 0
