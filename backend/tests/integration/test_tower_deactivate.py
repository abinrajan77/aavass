"""`tower_has_active_financials()` (app/services/tower.py) queries both `maintenance_dues`
and `special_collection_dues` for the tower — overview.md's acceptance criterion 8: "an
Overdue/Pending due blocks deactivation with 409 TOWER_HAS_ACTIVE_FINANCIALS"."""

from datetime import UTC, date, datetime

import pytest

from app.models.special_collection_due import SpecialCollectionDue
from tests.factories import (
    DEFAULT_PASSWORD,
    make_association_member,
    make_complex,
    make_flat,
    make_owner,
    make_role,
    make_special_collection,
    make_tower,
    make_user,
)


async def _login(client, email, password=DEFAULT_PASSWORD):
    return await client.post("/api/v1/auth/login", json={"email": email, "password": password})


@pytest.mark.asyncio
async def test_deactivate_succeeds_with_no_active_financials(client, db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    admin_role = await make_role(
        db_session,
        tower_id=tower.id,
        name="Admin",
        is_system_default=True,
        permission_codes=["MANAGE_COMPLEX", "VIEW_TOWER_DATA"],
    )
    admin_user = await make_user(db_session, email="deactivate-admin@example.com")
    await make_association_member(
        db_session, tower_id=tower.id, user_id=admin_user.id, role_id=admin_role.id
    )
    await db_session.commit()

    await _login(client, admin_user.email)

    resp = await client.post(f"/api/v1/towers/{tower.id}/deactivate")
    assert resp.status_code == 200
    assert resp.json()["deactivated_at"] is not None


@pytest.mark.asyncio
async def test_reactivate_requires_superuser_not_tower_admin(client, db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    admin_role = await make_role(
        db_session,
        tower_id=tower.id,
        name="Admin",
        is_system_default=True,
        permission_codes=["MANAGE_COMPLEX", "VIEW_TOWER_DATA"],
    )
    admin_user = await make_user(db_session, email="reactivate-admin@example.com")
    await make_association_member(
        db_session, tower_id=tower.id, user_id=admin_user.id, role_id=admin_role.id
    )
    await db_session.commit()

    await _login(client, admin_user.email)
    await client.post(f"/api/v1/towers/{tower.id}/deactivate")

    resp = await client.post(f"/api/v1/towers/{tower.id}/reactivate")
    assert resp.status_code == 403

    superuser = await make_user(
        db_session, email="reactivate-super@aavaas.internal", is_superuser=True
    )
    await db_session.commit()
    await _login(client, superuser.email)
    resp2 = await client.post(f"/api/v1/towers/{tower.id}/reactivate")
    assert resp2.status_code == 200
    assert resp2.json()["deactivated_at"] is None


@pytest.mark.asyncio
async def test_deactivate_blocked_by_pending_special_collection_due(client, db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    admin_role = await make_role(
        db_session,
        tower_id=tower.id,
        name="Admin",
        is_system_default=True,
        permission_codes=["MANAGE_COMPLEX", "MANAGE_SPECIAL_COLLECTIONS", "VIEW_TOWER_DATA"],
    )
    admin_user = await make_user(db_session, email="blocked-admin@example.com")
    admin_member = await make_association_member(
        db_session, tower_id=tower.id, user_id=admin_user.id, role_id=admin_role.id
    )
    flat = await make_flat(db_session, tower_id=tower.id)
    owner = await make_owner(db_session, full_name="Asha Rao")
    collection = await make_special_collection(
        db_session, tower_id=tower.id, created_by=admin_member.id
    )
    db_session.add(
        SpecialCollectionDue(
            special_collection_id=collection.id,
            tower_id=tower.id,
            flat_id=flat.id,
            flat_number=flat.flat_number,
            owner_id=owner.id,
            owner_name=owner.full_name,
            amount="500.00",
            due_date=date(2026, 9, 1),
            status="pending",
        )
    )
    await db_session.commit()

    await _login(client, admin_user.email)

    resp = await client.post(f"/api/v1/towers/{tower.id}/deactivate")
    assert resp.status_code == 409
    assert resp.json()["error_code"] == "TOWER_HAS_ACTIVE_FINANCIALS"


@pytest.mark.asyncio
async def test_deactivate_not_blocked_by_cancelled_special_collections_dues(client, db_session):
    """A cancelled special collection's leftover `pending` due rows are no longer money
    actually owed — they must not block tower deactivation (app/services/tower.py)."""
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    admin_role = await make_role(
        db_session,
        tower_id=tower.id,
        name="Admin",
        is_system_default=True,
        permission_codes=["MANAGE_COMPLEX", "MANAGE_SPECIAL_COLLECTIONS", "VIEW_TOWER_DATA"],
    )
    admin_user = await make_user(db_session, email="cancelled-admin@example.com")
    admin_member = await make_association_member(
        db_session, tower_id=tower.id, user_id=admin_user.id, role_id=admin_role.id
    )
    flat = await make_flat(db_session, tower_id=tower.id)
    owner = await make_owner(db_session, full_name="Asha Rao")
    collection = await make_special_collection(
        db_session, tower_id=tower.id, created_by=admin_member.id
    )
    collection.deactivated_at = datetime.now(UTC)
    db_session.add(
        SpecialCollectionDue(
            special_collection_id=collection.id,
            tower_id=tower.id,
            flat_id=flat.id,
            flat_number=flat.flat_number,
            owner_id=owner.id,
            owner_name=owner.full_name,
            amount="500.00",
            due_date=date(2026, 9, 1),
            status="pending",
        )
    )
    await db_session.commit()

    await _login(client, admin_user.email)

    resp = await client.post(f"/api/v1/towers/{tower.id}/deactivate")
    assert resp.status_code == 200
    assert resp.json()["deactivated_at"] is not None
