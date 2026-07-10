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


async def _make_admin(db_session, tower, permission_codes):
    role = await make_role(
        db_session, tower_id=tower.id, name="Admin", permission_codes=permission_codes
    )
    user = await make_user(db_session, email=f"admin-{tower.id}@example.com")
    await make_association_member(db_session, tower_id=tower.id, user_id=user.id, role_id=role.id)
    await db_session.commit()
    return user


@pytest.mark.asyncio
async def test_create_flat_and_list_it(client, db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    admin = await _make_admin(db_session, tower, ["MANAGE_RESIDENTS", "VIEW_TOWER_DATA"])
    await _login(client, admin.email)

    resp = await client.post(
        f"/api/v1/towers/{tower.id}/flats",
        json={"flat_number": "101", "floor": 1, "type": "2BHK", "carpet_area_sqft": "850.00"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["occupancy_status"] == "vacant"
    assert body["primary_owner"] is None
    assert body["active_tenant"] is None

    list_resp = await client.get(f"/api/v1/towers/{tower.id}/flats")
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1


@pytest.mark.asyncio
async def test_create_flat_with_duplicate_active_flat_number_returns_409(client, db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    admin = await _make_admin(db_session, tower, ["MANAGE_RESIDENTS", "VIEW_TOWER_DATA"])
    await _login(client, admin.email)

    payload = {"flat_number": "202", "floor": 2, "type": "3BHK", "carpet_area_sqft": "1200.00"}
    first = await client.post(f"/api/v1/towers/{tower.id}/flats", json=payload)
    assert first.status_code == 201

    second = await client.post(f"/api/v1/towers/{tower.id}/flats", json=payload)
    assert second.status_code == 409
    assert second.json()["error_code"] == "FLAT_NUMBER_TAKEN"


@pytest.mark.asyncio
async def test_update_flat_rejects_when_deactivated(client, db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    admin = await _make_admin(db_session, tower, ["MANAGE_RESIDENTS", "VIEW_TOWER_DATA"])
    await _login(client, admin.email)

    create_resp = await client.post(
        f"/api/v1/towers/{tower.id}/flats",
        json={"flat_number": "303", "floor": 3, "type": "1BHK", "carpet_area_sqft": "500.00"},
    )
    flat_id = create_resp.json()["id"]

    deactivate_resp = await client.post(f"/api/v1/towers/{tower.id}/flats/{flat_id}/deactivate")
    assert deactivate_resp.status_code == 200
    assert deactivate_resp.json()["deactivated_at"] is not None

    update_resp = await client.put(
        f"/api/v1/towers/{tower.id}/flats/{flat_id}", json={"floor": 4}
    )
    assert update_resp.status_code == 409
    assert update_resp.json()["error_code"] == "IMMUTABLE_RECORD"

    reactivate_resp = await client.post(
        f"/api/v1/towers/{tower.id}/flats/{flat_id}/reactivate"
    )
    assert reactivate_resp.status_code == 200
    assert reactivate_resp.json()["deactivated_at"] is None


@pytest.mark.asyncio
async def test_deactivate_succeeds_under_current_open_dues_stub(client, db_session):
    """Module 3/4's `maintenance_dues`/`special_collection_dues` tables don't exist yet, so
    `flat_has_open_dues()` (`app/services/flat.py`) is stubbed to always return `(False, 0)` —
    mirrors the identical, already-shipped stub pattern for
    `tower_has_active_financials()`/`test_tower_deactivate.py`. This asserts the *current,
    documented* stub behavior; revisit once Module 3/4 land and the stub is replaced with a
    real query, at which point `test_deactivate_returns_open_dues_exist_when_due_present`
    (not implementable against this module alone today) should be added.
    """
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    admin = await _make_admin(db_session, tower, ["MANAGE_RESIDENTS", "VIEW_TOWER_DATA"])
    await _login(client, admin.email)

    create_resp = await client.post(
        f"/api/v1/towers/{tower.id}/flats",
        json={"flat_number": "404", "floor": 4, "type": "OTHER", "carpet_area_sqft": "300.00"},
    )
    flat_id = create_resp.json()["id"]

    resp = await client.post(f"/api/v1/towers/{tower.id}/flats/{flat_id}/deactivate")
    assert resp.status_code == 200
    assert resp.json()["deactivated_at"] is not None


@pytest.mark.asyncio
async def test_list_flats_filters_by_type_and_occupancy_status(client, db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    admin = await _make_admin(db_session, tower, ["MANAGE_RESIDENTS", "VIEW_TOWER_DATA"])
    await _login(client, admin.email)

    await client.post(
        f"/api/v1/towers/{tower.id}/flats",
        json={"flat_number": "501", "floor": 5, "type": "1BHK", "carpet_area_sqft": "450.00"},
    )
    await client.post(
        f"/api/v1/towers/{tower.id}/flats",
        json={"flat_number": "502", "floor": 5, "type": "3BHK", "carpet_area_sqft": "1400.00"},
    )

    resp = await client.get(f"/api/v1/towers/{tower.id}/flats", params={"type": "1BHK"})
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["flat_number"] == "501"

    resp2 = await client.get(f"/api/v1/towers/{tower.id}/flats", params={"q": "502"})
    assert resp2.json()["total"] == 1


@pytest.mark.asyncio
async def test_admin_of_one_tower_cannot_read_another_towers_flats(client, db_session):
    complex_row = await make_complex(db_session)
    tower_a = await make_tower(db_session, complex_id=complex_row.id, name="Iso A", code="ISA")
    tower_b = await make_tower(db_session, complex_id=complex_row.id, name="Iso B", code="ISB")
    admin_a = await _make_admin(db_session, tower_a, ["MANAGE_RESIDENTS", "VIEW_TOWER_DATA"])
    await _make_admin(db_session, tower_b, ["MANAGE_RESIDENTS", "VIEW_TOWER_DATA"])
    await _login(client, admin_a.email)

    resp = await client.get(f"/api/v1/towers/{tower_b.id}/flats")
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "TOWER_ACCESS_DENIED"
