"""backend.md §8.2 — formula/grace-period versioning never retroacts onto historical cycles
(overview.md edge case 3, acceptance criterion 14). See
`test_billing_cycle_generation.py`'s module docstring re: sandbox runnability."""

import pytest
from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.billing_cycle import BillingCycle
from tests.factories import (
    DEFAULT_PASSWORD,
    make_billing_admin,
    make_complex,
    make_flat,
    make_maintenance_formula,
    make_owner,
    make_tower,
)


async def _login(client, email, password=DEFAULT_PASSWORD):
    return await client.post("/api/v1/auth/login", json={"email": email, "password": password})


@pytest.mark.asyncio
async def test_changing_the_formula_does_not_retroact_onto_a_generated_cycle(client, db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    member = await make_billing_admin(
        db_session, tower_id=tower.id, email="versioning-admin@example.com"
    )
    await make_maintenance_formula(
        db_session, tower_id=tower.id, created_by=member.id, base_amount=2000, per_sqft_rate=2
    )
    flat = await make_flat(db_session, tower_id=tower.id, carpet_area=850)
    await make_owner(db_session, flat_id=flat.id)
    await db_session.commit()

    await _login(client, "versioning-admin@example.com")

    create_resp = await client.post(
        f"/api/v1/towers/{tower.id}/billing-cycles",
        json={"month": 7, "year": 2026, "due_date": "2026-07-10"},
    )
    assert create_resp.status_code == 201
    cycle_body = create_resp.json()
    original_formula_id = cycle_body["formula_id"]
    original_due_amount = 2000 + 850 * 2  # base + area*rate = 3700.00

    # Now change the formula for *future* cycles.
    change_resp = await client.post(
        f"/api/v1/towers/{tower.id}/maintenance-formula",
        json={"base_amount": 5000.00, "per_sqft_rate": 10.00},
    )
    assert change_resp.status_code == 201

    # Re-fetch the historical cycle — must still report the original formula/amounts.
    refetch_resp = await client.get(f"/api/v1/towers/{tower.id}/billing-cycles/{cycle_body['id']}")
    assert refetch_resp.status_code == 200
    assert refetch_resp.json()["formula_id"] == original_formula_id

    dues_resp = await client.get(
        f"/api/v1/towers/{tower.id}/billing-cycles/{cycle_body['id']}/dues"
    )
    assert dues_resp.status_code == 200
    assert float(dues_resp.json()["items"][0]["amount"]) == original_due_amount


@pytest.mark.asyncio
async def test_changing_grace_period_does_not_retroact_onto_a_generated_cycles_snapshot(
    client, db_session
):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    member = await make_billing_admin(
        db_session, tower_id=tower.id, email="grace-versioning-admin@example.com"
    )
    await make_maintenance_formula(db_session, tower_id=tower.id, created_by=member.id)
    flat = await make_flat(db_session, tower_id=tower.id)
    await make_owner(db_session, flat_id=flat.id)
    await db_session.commit()

    await _login(client, "grace-versioning-admin@example.com")

    grace_resp = await client.post(
        f"/api/v1/towers/{tower.id}/grace-period-config", json={"grace_period_days": 5}
    )
    assert grace_resp.status_code == 201

    create_resp = await client.post(
        f"/api/v1/towers/{tower.id}/billing-cycles",
        json={"month": 8, "year": 2026, "due_date": "2026-08-10"},
    )
    cycle_id = create_resp.json()["id"]
    assert create_resp.json()["grace_period_days_snapshot"] == 5

    # Tower changes its grace period going forward.
    new_grace_resp = await client.post(
        f"/api/v1/towers/{tower.id}/grace-period-config", json={"grace_period_days": 10}
    )
    assert new_grace_resp.status_code == 201

    refetch = await client.get(f"/api/v1/towers/{tower.id}/billing-cycles/{cycle_id}")
    assert refetch.json()["grace_period_days_snapshot"] == 5  # unchanged

    cycle = await db_session.get(BillingCycle, cycle_id)
    assert cycle.grace_period_days_snapshot == 5


@pytest.mark.asyncio
async def test_formula_change_writes_audit_log_with_before_and_after(client, db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    member = await make_billing_admin(
        db_session, tower_id=tower.id, email="formula-audit-admin@example.com"
    )
    await make_maintenance_formula(
        db_session, tower_id=tower.id, created_by=member.id, base_amount=2000, per_sqft_rate=2
    )
    await db_session.commit()

    await _login(client, "formula-audit-admin@example.com")
    resp = await client.post(
        f"/api/v1/towers/{tower.id}/maintenance-formula",
        json={"base_amount": 2500.00, "per_sqft_rate": 3.00},
    )
    assert resp.status_code == 201
    new_id = resp.json()["id"]

    entry = await db_session.scalar(
        select(AuditLog).where(AuditLog.action == "formula_changed", AuditLog.entity_id == new_id)
    )
    assert entry is not None
    assert entry.before["base_amount"] == "2000.00" or entry.before["base_amount"] == "2000"
    assert entry.after["base_amount"] in ("2500.00", "2500")


@pytest.mark.asyncio
async def test_grace_period_change_writes_audit_log(client, db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    await make_billing_admin(db_session, tower_id=tower.id, email="grace-audit-admin@example.com")
    await db_session.commit()

    await _login(client, "grace-audit-admin@example.com")
    resp = await client.post(
        f"/api/v1/towers/{tower.id}/grace-period-config", json={"grace_period_days": 7}
    )
    assert resp.status_code == 201
    new_id = resp.json()["id"]

    entry = await db_session.scalar(
        select(AuditLog).where(
            AuditLog.action == "grace_period_changed", AuditLog.entity_id == new_id
        )
    )
    assert entry is not None
    assert entry.after["grace_period_days"] == 7
