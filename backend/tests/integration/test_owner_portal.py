"""Owner self-service portal — backend.md §3, overview.md acceptance criteria 7-8, backend test
plan's scoping/403 checks."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from app.services.payments import record_payment
from tests.factories import (
    DEFAULT_PASSWORD,
    make_association_member,
    make_billing_cycle,
    make_complex,
    make_flat,
    make_flat_ownership,
    make_maintenance_due,
    make_maintenance_formula,
    make_owner,
    make_role,
    make_tenant,
    make_tower,
    make_user,
)


async def _login(client, email, password=DEFAULT_PASSWORD):
    return await client.post("/api/v1/auth/login", json={"email": email, "password": password})


async def _make_billing_admin_member(db_session, *, tower_id):
    role = await make_role(
        db_session, tower_id=tower_id,
        permission_codes=[
            "CREATE_BILLING_CYCLE", "CONFIGURE_BILLING", "VIEW_TOWER_DATA", "MANAGE_RESIDENTS",
        ],
    )
    admin_user = await make_user(db_session, email=f"tower-admin-{uuid4()}@example.com")
    member = await make_association_member(
        db_session, tower_id=tower_id, user_id=admin_user.id, role_id=role.id
    )
    return admin_user, member


@pytest.mark.asyncio
async def test_flats_summary_groups_flats_across_towers_by_tower(client, db_session):
    complex_row = await make_complex(db_session)
    tower_a = await make_tower(db_session, complex_id=complex_row.id, name="Tower A", code="TWA")
    tower_b = await make_tower(db_session, complex_id=complex_row.id, name="Tower B", code="TWB")

    owner_user = await make_user(
        db_session, email="multi-owner@example.com", account_type="flat_owner"
    )
    owner = await make_owner(db_session, full_name="Multi Owner", user_id=owner_user.id)

    flat_a = await make_flat(
        db_session, tower_id=tower_a.id, flat_number="101", occupancy_status="owner_occupied"
    )
    flat_b = await make_flat(
        db_session, tower_id=tower_b.id, flat_number="202", occupancy_status="vacant"
    )
    await make_flat_ownership(
        db_session, flat_id=flat_a.id, owner_id=owner.id, created_by_user_id=owner_user.id,
        is_primary_contact=True,
    )
    await make_flat_ownership(
        db_session, flat_id=flat_b.id, owner_id=owner.id, created_by_user_id=owner_user.id,
        is_primary_contact=True,
    )
    await db_session.commit()

    await _login(client, owner_user.email)
    resp = await client.get("/api/v1/owners/me/flats-summary")
    assert resp.status_code == 200
    body = resp.json()
    tower_ids = {t["tower_id"] for t in body["towers"]}
    assert str(tower_a.id) in tower_ids
    assert str(tower_b.id) in tower_ids
    flat_numbers = {
        flat["flat_number"] for t in body["towers"] for flat in t["flats"]
    }
    assert flat_numbers == {"101", "202"}
    for tower_block in body["towers"]:
        for flat in tower_block["flats"]:
            if flat["flat_number"] == "202":
                assert flat["current_due_status"] == "no_active_due"


@pytest.mark.asyncio
async def test_flats_summary_excludes_sold_flat(client, db_session):
    """backend test plan: never returns a flat where the caller's FlatOwnership.date_to is
    set — no include_history flag exists in v1.0 to bring it back."""
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    owner_user = await make_user(db_session, email="seller@example.com", account_type="flat_owner")
    owner = await make_owner(db_session, full_name="Seller Owner", user_id=owner_user.id)
    flat = await make_flat(db_session, tower_id=tower.id, flat_number="303")
    ownership = await make_flat_ownership(
        db_session, flat_id=flat.id, owner_id=owner.id, created_by_user_id=owner_user.id,
        is_primary_contact=True,
    )
    await db_session.commit()

    await _login(client, owner_user.email)
    resp_before = await client.get("/api/v1/owners/me/flats-summary")
    flats_before = [f["flat_number"] for t in resp_before.json()["towers"] for f in t["flats"]]
    assert "303" in flats_before

    ownership.date_to = date(2026, 1, 1)
    await db_session.commit()

    resp_after = await client.get("/api/v1/owners/me/flats-summary")
    flats_after = [f["flat_number"] for t in resp_after.json()["towers"] for f in t["flats"]]
    assert "303" not in flats_after


@pytest.mark.asyncio
async def test_dashboard_returns_403_for_flat_never_owned(client, db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    owner_user = await make_user(
        db_session, email="onlooker@example.com", account_type="flat_owner"
    )
    await make_owner(db_session, full_name="Onlooker Owner", user_id=owner_user.id)
    other_flat = await make_flat(db_session, tower_id=tower.id, flat_number="404")
    await db_session.commit()

    await _login(client, owner_user.email)
    resp = await client.get(f"/api/v1/owners/me/flats/{other_flat.id}/dashboard")
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "OWNERSHIP_NOT_FOUND"


@pytest.mark.asyncio
async def test_dashboard_returns_403_for_previously_owned_flat(client, db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    owner_user = await make_user(
        db_session, email="ex-owner@example.com", account_type="flat_owner"
    )
    owner = await make_owner(db_session, full_name="Ex Owner", user_id=owner_user.id)
    flat = await make_flat(db_session, tower_id=tower.id, flat_number="505")
    await make_flat_ownership(
        db_session, flat_id=flat.id, owner_id=owner.id, created_by_user_id=owner_user.id,
        is_primary_contact=True, date_to=date(2025, 1, 1),
    )
    await db_session.commit()

    await _login(client, owner_user.email)
    resp = await client.get(f"/api/v1/owners/me/flats/{flat.id}/dashboard")
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "OWNERSHIP_NOT_FOUND"


@pytest.mark.asyncio
async def test_dashboard_includes_current_due_history_receipts_and_tenant_history(
    client, db_session
):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    admin_user, member = await _make_billing_admin_member(db_session, tower_id=tower.id)
    formula = await make_maintenance_formula(db_session, tower_id=tower.id, created_by=member.id)
    cycle = await make_billing_cycle(
        db_session, tower_id=tower.id, formula_id=formula.id, created_by=member.id,
        month=7, year=2026,
    )

    owner_user = await make_user(
        db_session, email="dashboard-owner@example.com", account_type="flat_owner"
    )
    owner = await make_owner(db_session, full_name="Dashboard Owner", user_id=owner_user.id)
    flat = await make_flat(
        db_session, tower_id=tower.id, flat_number="606", occupancy_status="owner_occupied"
    )
    await make_flat_ownership(
        db_session, flat_id=flat.id, owner_id=owner.id, created_by_user_id=owner_user.id,
        is_primary_contact=True,
    )

    # Past tenant (pre-dates current ownership) — tenant history must still show it.
    await make_tenant(
        db_session, flat_id=flat.id, full_name="Old Tenant", lease_start=date(2020, 1, 1),
        lease_end=date(2021, 1, 1), is_active=False,
    )

    due = await make_maintenance_due(
        db_session, billing_cycle_id=cycle.id, tower_id=tower.id, flat_id=flat.id,
        primary_owner_id=owner.id, assigned_to_type="owner", assigned_to_id=owner.id,
        assigned_to_name_snapshot=owner.full_name, amount=Decimal("2000.00"),
    )
    await db_session.commit()

    receipt = await record_payment(
        db_session, tower_id=tower.id, due_type="maintenance", due_id=due.id,
        payment_date=date(2026, 7, 8), amount_received=Decimal("2000.00"), payment_mode="cash",
        reference_number=None, recorded_by=member,
    )

    await _login(client, owner_user.email)
    resp = await client.get(f"/api/v1/owners/me/flats/{flat.id}/dashboard")
    assert resp.status_code == 200
    body = resp.json()
    assert body["flat_number"] == "606"
    assert body["current_due"]["status"] == "paid"
    assert len(body["payment_history"]) == 1
    assert len(body["receipts"]) == 1
    assert body["receipts"][0]["receipt_number"] == receipt.receipt_number
    tenant_names = {t["tenant_name"] for t in body["tenant_history"]}
    assert "Old Tenant" in tenant_names
    assert Decimal(body["ytd_totals"]["total_paid_ytd"]) == Decimal("2000.00")


@pytest.mark.asyncio
async def test_non_owner_account_gets_403_not_a_flat_owner(client, db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    role = await make_role(db_session, tower_id=tower.id, permission_codes=["VIEW_TOWER_DATA"])
    plain_user = await make_user(db_session, email="not-owner@example.com")
    await make_association_member(
        db_session, tower_id=tower.id, user_id=plain_user.id, role_id=role.id
    )
    await db_session.commit()

    await _login(client, plain_user.email)
    resp = await client.get("/api/v1/owners/me/flats-summary")
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "NOT_A_FLAT_OWNER"
