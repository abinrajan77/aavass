import pytest

from tests.factories import (
    DEFAULT_PASSWORD,
    make_association_member,
    make_complex,
    make_flat,
    make_role,
    make_tower,
    make_user,
)


async def _login(client, email, password=DEFAULT_PASSWORD):
    return await client.post("/api/v1/auth/login", json={"email": email, "password": password})


async def _make_admin(db_session, tower, permission_codes):
    role = await make_role(
        db_session, tower_id=tower.id, name="Admin", permission_codes=permission_codes
    )
    user = await make_user(db_session, email=f"owner-admin-{tower.id}@example.com")
    await make_association_member(db_session, tower_id=tower.id, user_id=user.id, role_id=role.id)
    await db_session.commit()
    return user


@pytest.mark.asyncio
async def test_first_owner_added_via_api_becomes_primary_owner_on_flat(client, db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    flat = await make_flat(db_session, tower_id=tower.id)
    admin = await _make_admin(db_session, tower, ["MANAGE_RESIDENTS", "VIEW_TOWER_DATA"])
    await db_session.commit()
    await _login(client, admin.email)

    resp = await client.post(
        f"/api/v1/towers/{tower.id}/flats/{flat.id}/owners",
        json={
            "full_name": "New Owner",
            "phone": "9887766554",
            "is_primary_contact": False,
            "date_from": "2024-01-01",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["is_primary_contact"] is True

    flat_resp = await client.get(f"/api/v1/towers/{tower.id}/flats/{flat.id}")
    assert flat_resp.json()["primary_owner"]["full_name"] == "New Owner"


@pytest.mark.asyncio
async def test_remove_sole_owner_returns_409_last_owner_on_flat(client, db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    flat = await make_flat(db_session, tower_id=tower.id)
    admin = await _make_admin(db_session, tower, ["MANAGE_RESIDENTS", "VIEW_TOWER_DATA"])
    await db_session.commit()
    await _login(client, admin.email)

    add_resp = await client.post(
        f"/api/v1/towers/{tower.id}/flats/{flat.id}/owners",
        json={"full_name": "Sole Owner", "phone": "9887766001", "date_from": "2024-01-01"},
    )
    ownership_id = add_resp.json()["id"]

    remove_resp = await client.post(
        f"/api/v1/towers/{tower.id}/flats/{flat.id}/owners/{ownership_id}/remove",
        json={"effective_date": "2024-06-01"},
    )
    assert remove_resp.status_code == 409
    assert remove_resp.json()["error_code"] == "LAST_OWNER_ON_FLAT"


@pytest.mark.asyncio
async def test_remove_primary_owner_requires_new_primary_owner_id(client, db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    flat = await make_flat(db_session, tower_id=tower.id)
    admin = await _make_admin(db_session, tower, ["MANAGE_RESIDENTS", "VIEW_TOWER_DATA"])
    await db_session.commit()
    await _login(client, admin.email)

    primary_resp = await client.post(
        f"/api/v1/towers/{tower.id}/flats/{flat.id}/owners",
        json={"full_name": "Primary Owner", "phone": "9887766002", "date_from": "2024-01-01"},
    )
    primary_ownership_id = primary_resp.json()["id"]
    co_owner_resp = await client.post(
        f"/api/v1/towers/{tower.id}/flats/{flat.id}/owners",
        json={
            "full_name": "Co Owner",
            "phone": "9887766003",
            "is_primary_contact": False,
            "date_from": "2024-01-01",
        },
    )
    co_owner_id = co_owner_resp.json()["owner_id"]

    without_new_primary = await client.post(
        f"/api/v1/towers/{tower.id}/flats/{flat.id}/owners/{primary_ownership_id}/remove",
        json={"effective_date": "2024-06-01"},
    )
    assert without_new_primary.status_code == 409
    assert without_new_primary.json()["error_code"] == "PRIMARY_CONTACT_REQUIRED"

    with_new_primary = await client.post(
        f"/api/v1/towers/{tower.id}/flats/{flat.id}/owners/{primary_ownership_id}/remove",
        json={"effective_date": "2024-06-01", "new_primary_owner_id": co_owner_id},
    )
    assert with_new_primary.status_code == 200

    owners_resp = await client.get(f"/api/v1/towers/{tower.id}/flats/{flat.id}/owners")
    rows = owners_resp.json()["items"]
    active_primary = [r for r in rows if r["date_to"] is None and r["is_primary_contact"]]
    assert len(active_primary) == 1
    assert active_primary[0]["owner_id"] == co_owner_id
