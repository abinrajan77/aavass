import pytest
from sqlalchemy import func, select

from app.models.user import User
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


@pytest.mark.asyncio
async def test_creating_member_with_existing_email_links_existing_user_not_duplicate(
    client, db_session
):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    admin_role = await make_role(
        db_session,
        tower_id=tower.id,
        name="Admin",
        is_system_default=True,
        permission_codes=["MANAGE_ASSOCIATION_MEMBERS", "VIEW_TOWER_DATA"],
    )
    treasurer_role = await make_role(
        db_session, tower_id=tower.id, name="Treasurer", permission_codes=["RECORD_PAYMENT"]
    )
    admin_user = await make_user(db_session, email="member-admin@example.com")
    await make_association_member(
        db_session, tower_id=tower.id, user_id=admin_user.id, role_id=admin_role.id
    )

    # Pre-existing user, e.g. provisioned as a flat owner by Module 2 (simulated here).
    existing_user = await make_user(
        db_session, email="dual-role@example.com", account_type="flat_owner"
    )
    await db_session.commit()

    await _login(client, admin_user.email)

    resp = await client.post(
        f"/api/v1/towers/{tower.id}/association-members",
        json={
            "name": "Dual Role Person",
            "email": "dual-role@example.com",
            "phone": "9876543210",
            "role_id": str(treasurer_role.id),
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["association_member"]["user_id"] == str(existing_user.id)
    assert "temporary_password" in body

    user_count = await db_session.scalar(
        select(func.count()).select_from(User).where(User.email == "dual-role@example.com")
    )
    assert user_count == 1


@pytest.mark.asyncio
async def test_deactivating_the_only_active_admin_returns_409_last_admin(client, db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    admin_role = await make_role(
        db_session,
        tower_id=tower.id,
        name="Admin",
        is_system_default=True,
        permission_codes=["MANAGE_ASSOCIATION_MEMBERS", "VIEW_TOWER_DATA"],
    )
    admin_user = await make_user(db_session, email="sole-admin@example.com")
    member = await make_association_member(
        db_session, tower_id=tower.id, user_id=admin_user.id, role_id=admin_role.id
    )
    await db_session.commit()

    await _login(client, admin_user.email)

    resp = await client.post(
        f"/api/v1/towers/{tower.id}/association-members/{member.id}/deactivate"
    )
    assert resp.status_code == 409
    assert resp.json()["error_code"] == "LAST_ADMIN"

    await db_session.refresh(member)
    assert member.deactivated_at is None


@pytest.mark.asyncio
async def test_deactivating_one_of_two_admins_succeeds(client, db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    admin_role = await make_role(
        db_session,
        tower_id=tower.id,
        name="Admin",
        is_system_default=True,
        permission_codes=["MANAGE_ASSOCIATION_MEMBERS", "VIEW_TOWER_DATA"],
    )
    user1 = await make_user(db_session, email="admin-one@example.com")
    user2 = await make_user(db_session, email="admin-two@example.com")
    member1 = await make_association_member(
        db_session, tower_id=tower.id, user_id=user1.id, role_id=admin_role.id
    )
    await make_association_member(
        db_session, tower_id=tower.id, user_id=user2.id, role_id=admin_role.id
    )
    await db_session.commit()

    await _login(client, user1.email)

    resp = await client.post(
        f"/api/v1/towers/{tower.id}/association-members/{member1.id}/deactivate"
    )
    assert resp.status_code == 200
    assert resp.json()["deactivated_at"] is not None
