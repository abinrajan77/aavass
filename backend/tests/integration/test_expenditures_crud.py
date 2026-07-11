"""Basic CRUD + RBAC coverage for expenditures beyond backend.md's numbered test-plan items
(9-12 are covered in `test_expenditures.py`) — create/get/update/delete, audit log entries,
and independence of `MANAGE_EXPENDITURE` from `MANAGE_SPECIAL_COLLECTIONS`/`RECORD_PAYMENT`
(backend.md "What must NOT break" section)."""

from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models.audit_log import AuditLog
from tests.factories import (
    DEFAULT_PASSWORD,
    make_association_member,
    make_complex,
    make_role,
    make_tower,
    make_user,
)


async def _login(client, email, password=DEFAULT_PASSWORD):
    return await client.post("/api/v1/auth/login", json={"email": email, "password": password})


async def _setup_tower_with_admin(db_session, *, permission_codes):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    role = await make_role(db_session, tower_id=tower.id, permission_codes=permission_codes)
    user = await make_user(db_session, email=f"admin-{uuid4()}@example.com")
    await make_association_member(db_session, tower_id=tower.id, user_id=user.id, role_id=role.id)
    await db_session.commit()
    return tower, user


@pytest.mark.asyncio
async def test_expenditure_create_get_update_delete_round_trip(client, db_session):
    tower, user = await _setup_tower_with_admin(
        db_session, permission_codes=["MANAGE_EXPENDITURE", "VIEW_TOWER_DATA"]
    )
    await _login(client, user.email)

    create_resp = await client.post(
        f"/api/v1/towers/{tower.id}/expenditures",
        json={
            "expenditure_date": "2026-07-05",
            "category": "security",
            "description": "Guard salaries",
            "vendor_payee_name": "SecureCo",
            "amount": "20000.00",
            "payment_mode": "bank_transfer",
        },
    )
    assert create_resp.status_code == 201
    expenditure_id = create_resp.json()["id"]

    get_resp = await client.get(f"/api/v1/towers/{tower.id}/expenditures/{expenditure_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["vendor_payee_name"] == "SecureCo"

    update_resp = await client.put(
        f"/api/v1/towers/{tower.id}/expenditures/{expenditure_id}",
        json={"amount": "21000.00", "description": "Guard salaries (revised)"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["amount"] == "21000.00"
    assert update_resp.json()["description"] == "Guard salaries (revised)"

    entries = (
        await db_session.execute(
            select(AuditLog)
            .where(AuditLog.entity_type == "Expenditure", AuditLog.entity_id == expenditure_id)
            .order_by(AuditLog.created_at.asc())
        )
    ).scalars().all()
    actions = [e.action for e in entries]
    assert "EXPENDITURE_CREATED" in actions
    assert "EXPENDITURE_UPDATED" in actions
    updated_entry = next(e for e in entries if e.action == "EXPENDITURE_UPDATED")
    assert updated_entry.before["amount"] == "20000.00"
    assert updated_entry.after["amount"] == "21000.00"

    delete_resp = await client.delete(f"/api/v1/towers/{tower.id}/expenditures/{expenditure_id}")
    assert delete_resp.status_code == 200
    assert delete_resp.json()["deactivated_at"] is not None

    # Deleting twice is rejected rather than silently no-op'd.
    second_delete = await client.delete(f"/api/v1/towers/{tower.id}/expenditures/{expenditure_id}")
    assert second_delete.status_code == 409


@pytest.mark.asyncio
async def test_manage_expenditure_permission_is_independent_of_manage_special_collections(
    client, db_session
):
    tower, user = await _setup_tower_with_admin(
        db_session, permission_codes=["MANAGE_SPECIAL_COLLECTIONS", "VIEW_TOWER_DATA"]
    )
    await _login(client, user.email)

    resp = await client.post(
        f"/api/v1/towers/{tower.id}/expenditures",
        json={
            "expenditure_date": "2026-07-05",
            "category": "utilities",
            "description": "Electricity bill",
            "vendor_payee_name": "State Electricity Board",
            "amount": "15000.00",
            "payment_mode": "bank_transfer",
        },
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "PERMISSION_DENIED"


@pytest.mark.asyncio
async def test_manage_special_collections_permission_is_independent_of_manage_expenditure(
    client, db_session
):
    tower, user = await _setup_tower_with_admin(
        db_session, permission_codes=["MANAGE_EXPENDITURE", "VIEW_TOWER_DATA"]
    )
    await _login(client, user.email)

    resp = await client.post(
        f"/api/v1/towers/{tower.id}/special-collections",
        json={"title": "Should be denied", "total_amount": "1000.00", "due_date": "2026-09-01"},
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "PERMISSION_DENIED"
