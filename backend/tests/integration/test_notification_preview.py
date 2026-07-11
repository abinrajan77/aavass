"""Notification preview endpoint — backend.md §4, overview.md acceptance criteria 9-10."""

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


async def _setup_reports_admin(db_session, *, permission_codes=None):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    role = await make_role(
        db_session, tower_id=tower.id,
        permission_codes=permission_codes or ["VIEW_REPORTS", "VIEW_TOWER_DATA"],
    )
    user = await make_user(db_session, email=f"reports-admin-{uuid4()}@example.com")
    member = await make_association_member(
        db_session, tower_id=tower.id, user_id=user.id, role_id=role.id
    )
    await db_session.commit()
    return tower, user, member


async def _make_due(db_session, *, tower, member, occupancy_status):
    formula = await make_maintenance_formula(db_session, tower_id=tower.id, created_by=member.id)
    cycle = await make_billing_cycle(
        db_session, tower_id=tower.id, formula_id=formula.id, created_by=member.id,
        month=7, year=2026,
    )
    flat = await make_flat(
        db_session, tower_id=tower.id, flat_number="801", occupancy_status=occupancy_status
    )
    owner = await make_owner(db_session, full_name="Notif Owner", phone="9000000001")
    await make_flat_ownership(
        db_session, flat_id=flat.id, owner_id=owner.id, created_by_user_id=member.user_id,
        is_primary_contact=True,
    )
    tenant = None
    if occupancy_status == "tenant_occupied":
        tenant = await make_tenant(
            db_session, flat_id=flat.id, full_name="Notif Tenant", phone="9000000002"
        )

    due = await make_maintenance_due(
        db_session, billing_cycle_id=cycle.id, tower_id=tower.id, flat_id=flat.id,
        primary_owner_id=owner.id,
        assigned_to_type="tenant" if tenant is not None else "owner",
        assigned_to_id=tenant.id if tenant is not None else owner.id,
        assigned_to_name_snapshot=tenant.full_name if tenant is not None else owner.full_name,
        amount=Decimal("2500.00"), due_date=date(2026, 7, 10),
    )
    await db_session.commit()
    return flat, owner, tenant, due


@pytest.mark.asyncio
async def test_preview_tenant_occupied_returns_two_messages(client, db_session):
    tower, user, member = await _setup_reports_admin(db_session)
    flat, owner, tenant, due = await _make_due(
        db_session, tower=tower, member=member, occupancy_status="tenant_occupied"
    )

    await _login(client, user.email)
    resp = await client.get(
        "/api/v1/notifications/templates/preview",
        params={"event": "due_generated", "due_id": str(due.id), "due_type": "maintenance"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["flat_number"] == "801"
    assert len(body["messages"]) == 2
    recipients = {m["recipient"] for m in body["messages"]}
    assert recipients == {"tenant", "owner"}
    tenant_msg = next(m for m in body["messages"] if m["recipient"] == "tenant")
    owner_msg = next(m for m in body["messages"] if m["recipient"] == "owner")
    assert tenant_msg["recipient_name"] == "Notif Tenant"
    assert "Notif Tenant" in tenant_msg["message_text"]
    assert "2500.00" in tenant_msg["message_text"]
    assert owner_msg["recipient_name"] == "Notif Owner"
    assert "Notif Tenant" in owner_msg["message_text"]  # owner_copy mentions the resident
    # No delivery-status field / send action anywhere in the response.
    assert "delivery_status" not in body
    for message in body["messages"]:
        assert "status" not in message


@pytest.mark.asyncio
async def test_preview_owner_occupied_returns_one_message(client, db_session):
    tower, user, member = await _setup_reports_admin(db_session)
    flat, owner, tenant, due = await _make_due(
        db_session, tower=tower, member=member, occupancy_status="owner_occupied"
    )

    await _login(client, user.email)
    resp = await client.get(
        "/api/v1/notifications/templates/preview",
        params={"event": "payment_confirmed", "due_id": str(due.id), "due_type": "maintenance"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["messages"]) == 1
    assert body["messages"][0]["recipient"] == "owner"
    assert body["messages"][0]["recipient_name"] == "Notif Owner"


@pytest.mark.asyncio
async def test_preview_requires_view_reports_permission(client, db_session):
    tower, user, member = await _setup_reports_admin(
        db_session, permission_codes=["VIEW_TOWER_DATA"]
    )
    flat, owner, tenant, due = await _make_due(
        db_session, tower=tower, member=member, occupancy_status="owner_occupied"
    )

    await _login(client, user.email)
    resp = await client.get(
        "/api/v1/notifications/templates/preview",
        params={"event": "due_generated", "due_id": str(due.id), "due_type": "maintenance"},
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "PERMISSION_DENIED"


@pytest.mark.asyncio
async def test_preview_unknown_due_returns_404(client, db_session):
    tower, user, _member = await _setup_reports_admin(db_session)
    await db_session.commit()
    await _login(client, user.email)
    resp = await client.get(
        "/api/v1/notifications/templates/preview",
        params={"event": "due_generated", "due_id": str(uuid4()), "due_type": "maintenance"},
    )
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "DUE_NOT_FOUND"


@pytest.mark.asyncio
async def test_preview_no_resident_resolved_returns_422(client, db_session):
    """overview.md defensive edge case: a due with no resolvable resident returns 422 rather
    than a template rendered with blank placeholders."""
    tower, user, member = await _setup_reports_admin(db_session)
    formula = await make_maintenance_formula(db_session, tower_id=tower.id, created_by=member.id)
    cycle = await make_billing_cycle(
        db_session, tower_id=tower.id, formula_id=formula.id, created_by=member.id
    )
    flat = await make_flat(
        db_session, tower_id=tower.id, flat_number="901", occupancy_status="vacant"
    )
    owner = await make_owner(db_session, full_name="Orphan Owner")
    # No FlatOwnership created — flat has no active primary owner and is vacant (no tenant).
    due = await make_maintenance_due(
        db_session, billing_cycle_id=cycle.id, tower_id=tower.id, flat_id=flat.id,
        primary_owner_id=owner.id, assigned_to_type="owner", assigned_to_id=owner.id,
        assigned_to_name_snapshot=owner.full_name,
    )
    await db_session.commit()

    await _login(client, user.email)
    resp = await client.get(
        "/api/v1/notifications/templates/preview",
        params={"event": "due_generated", "due_id": str(due.id), "due_type": "maintenance"},
    )
    assert resp.status_code == 422
    assert resp.json()["error_code"] == "NO_RESIDENT_RESOLVED"
