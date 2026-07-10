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
async def test_tower_a_admin_cannot_read_tower_b_association_members(client, db_session):
    complex_row = await make_complex(db_session)
    tower_a = await make_tower(db_session, complex_id=complex_row.id, name="Tower A", code="TWA")
    tower_b = await make_tower(db_session, complex_id=complex_row.id, name="Tower B", code="TWB")
    role_a = await make_role(
        db_session, tower_id=tower_a.id, name="Admin A", permission_codes=["VIEW_TOWER_DATA"]
    )
    user = await make_user(db_session, email="tower-a-admin@example.com")
    await make_association_member(
        db_session, tower_id=tower_a.id, user_id=user.id, role_id=role_a.id
    )
    await db_session.commit()

    login_resp = await _login(client, user.email)
    assert login_resp.status_code == 200

    resp_a = await client.get(f"/api/v1/towers/{tower_a.id}/association-members")
    assert resp_a.status_code == 200

    resp_b = await client.get(f"/api/v1/towers/{tower_b.id}/association-members")
    assert resp_b.status_code == 403
    assert resp_b.json()["error_code"] == "TOWER_ACCESS_DENIED"


@pytest.mark.asyncio
async def test_cross_tower_isolation_holds_under_pagination(client, db_session):
    complex_row = await make_complex(db_session)
    tower_a = await make_tower(db_session, complex_id=complex_row.id, name="Tower A2", code="TA2")
    tower_b = await make_tower(db_session, complex_id=complex_row.id, name="Tower B2", code="TB2")
    role_a = await make_role(
        db_session,
        tower_id=tower_a.id,
        name="Admin A2",
        permission_codes=["VIEW_TOWER_DATA", "MANAGE_ASSOCIATION_MEMBERS"],
    )
    role_b = await make_role(
        db_session,
        tower_id=tower_b.id,
        name="Admin B2",
        permission_codes=["VIEW_TOWER_DATA", "MANAGE_ASSOCIATION_MEMBERS"],
    )
    admin_user = await make_user(db_session, email="admin-a2@example.com")
    await make_association_member(
        db_session, tower_id=tower_a.id, user_id=admin_user.id, role_id=role_a.id
    )

    # Populate Tower B with several members that must never leak into Tower A's paginated list.
    for i in range(5):
        u = await make_user(db_session, email=f"member-b-{i}@example.com")
        await make_association_member(
            db_session, tower_id=tower_b.id, user_id=u.id, role_id=role_b.id
        )

    await db_session.commit()

    login_resp = await _login(client, admin_user.email)
    assert login_resp.status_code == 200

    # Even with a crafted page/page_size, Tower A's admin must never see Tower B's rows —
    # and must not be able to read Tower B's list at all regardless of query params.
    resp = await client.get(
        f"/api/v1/towers/{tower_b.id}/association-members", params={"page": 1, "page_size": 100}
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_page_size_beyond_max_is_422_not_silently_clamped(client, db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    role = await make_role(db_session, tower_id=tower.id, permission_codes=["VIEW_TOWER_DATA"])
    user = await make_user(db_session, email="page-size-test@example.com")
    await make_association_member(db_session, tower_id=tower.id, user_id=user.id, role_id=role.id)
    await db_session.commit()

    await _login(client, user.email)
    resp = await client.get(
        f"/api/v1/towers/{tower.id}/association-members", params={"page": 1, "page_size": 101}
    )
    assert resp.status_code == 422
    assert resp.json()["error_code"] == "VALIDATION_ERROR"
    assert resp.json()["field_errors"]
