import pytest

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
async def test_put_against_system_default_admin_role_returns_409_role_immutable(client, db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    admin_role = await make_role(
        db_session,
        tower_id=tower.id,
        name="Admin",
        is_system_default=True,
        permission_codes=["MANAGE_ASSOCIATION_MEMBERS", "VIEW_TOWER_DATA"],
    )
    admin_user = await make_user(db_session, email="immutable-admin@example.com")
    await make_association_member(
        db_session, tower_id=tower.id, user_id=admin_user.id, role_id=admin_role.id
    )
    await db_session.commit()

    await _login(client, admin_user.email)

    resp = await client.put(
        f"/api/v1/towers/{tower.id}/roles/{admin_role.id}",
        json={"permission_codes": ["VIEW_TOWER_DATA"]},
    )
    assert resp.status_code == 409
    assert resp.json()["error_code"] == "ROLE_IMMUTABLE"

    await db_session.refresh(admin_role, attribute_names=["permissions"])
    codes = {p.code for p in admin_role.permissions}
    assert "MANAGE_ASSOCIATION_MEMBERS" in codes  # unchanged


@pytest.mark.asyncio
async def test_deactivating_system_default_admin_role_returns_409_role_immutable(
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
    admin_user = await make_user(db_session, email="immutable-admin-2@example.com")
    await make_association_member(
        db_session, tower_id=tower.id, user_id=admin_user.id, role_id=admin_role.id
    )
    await db_session.commit()

    await _login(client, admin_user.email)

    resp = await client.post(f"/api/v1/towers/{tower.id}/roles/{admin_role.id}/deactivate")
    assert resp.status_code == 409
    assert resp.json()["error_code"] == "ROLE_IMMUTABLE"


@pytest.mark.asyncio
async def test_deactivating_a_role_still_held_by_active_member_returns_409_role_in_use(
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
    admin_user = await make_user(db_session, email="role-in-use-admin@example.com")
    await make_association_member(
        db_session, tower_id=tower.id, user_id=admin_user.id, role_id=admin_role.id
    )
    treasurer_user = await make_user(db_session, email="treasurer-holder@example.com")
    await make_association_member(
        db_session, tower_id=tower.id, user_id=treasurer_user.id, role_id=treasurer_role.id
    )
    await db_session.commit()

    await _login(client, admin_user.email)

    resp = await client.post(f"/api/v1/towers/{tower.id}/roles/{treasurer_role.id}/deactivate")
    assert resp.status_code == 409
    assert resp.json()["error_code"] == "ROLE_IN_USE"
