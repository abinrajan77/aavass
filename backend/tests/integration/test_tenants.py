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
    user = await make_user(db_session, email=f"tenant-admin-{tower.id}@example.com")
    await make_association_member(db_session, tower_id=tower.id, user_id=user.id, role_id=role.id)
    await db_session.commit()
    return user


@pytest.mark.asyncio
async def test_create_tenant_with_lease_start_after_lease_end_returns_422(client, db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    flat = await make_flat(db_session, tower_id=tower.id)
    admin = await _make_admin(db_session, tower, ["MANAGE_RESIDENTS", "VIEW_TOWER_DATA"])
    await db_session.commit()
    await _login(client, admin.email)

    resp = await client.post(
        f"/api/v1/towers/{tower.id}/flats/{flat.id}/tenants",
        json={
            "full_name": "Bad Dates Tenant",
            "phone": "9111122223",
            "lease_start": "2024-06-01",
            "lease_end": "2024-01-01",
        },
    )
    assert resp.status_code == 422
    assert resp.json()["error_code"] == "VALIDATION_ERROR"
    assert "lease_end" in resp.json()["field_errors"]


@pytest.mark.asyncio
async def test_vacate_tenant_persists_exactly_vacant_not_owner_occupied(client, db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    flat = await make_flat(db_session, tower_id=tower.id)
    admin = await _make_admin(db_session, tower, ["MANAGE_RESIDENTS", "VIEW_TOWER_DATA"])
    await db_session.commit()
    await _login(client, admin.email)

    create_resp = await client.post(
        f"/api/v1/towers/{tower.id}/flats/{flat.id}/tenants",
        json={"full_name": "Vacate Tenant", "phone": "9111133334", "lease_start": "2024-01-01"},
    )
    assert create_resp.status_code == 201
    tenant_id = create_resp.json()["id"]

    get_after_create = await client.get(f"/api/v1/towers/{tower.id}/flats/{flat.id}")
    assert get_after_create.json()["occupancy_status"] == "tenant_occupied"

    vacate_resp = await client.post(
        f"/api/v1/towers/{tower.id}/flats/{flat.id}/tenants/{tenant_id}/vacate",
        json={"vacated_date": "2024-12-01", "occupancy_status": "vacant"},
    )
    assert vacate_resp.status_code == 200
    assert vacate_resp.json()["is_active"] is False

    # Assert via a follow-up GET, not just the response body, to catch a bug where the code
    # defaults to "owner_occupied".
    get_resp = await client.get(f"/api/v1/towers/{tower.id}/flats/{flat.id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["occupancy_status"] == "vacant"
    assert get_resp.json()["active_tenant"] is None


@pytest.mark.asyncio
async def test_second_tenant_on_occupied_flat_returns_409_and_db_has_exactly_one_active(
    client, db_session
):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    flat = await make_flat(db_session, tower_id=tower.id)
    admin = await _make_admin(db_session, tower, ["MANAGE_RESIDENTS", "VIEW_TOWER_DATA"])
    await db_session.commit()
    await _login(client, admin.email)

    first = await client.post(
        f"/api/v1/towers/{tower.id}/flats/{flat.id}/tenants",
        json={"full_name": "First", "phone": "9111144445", "lease_start": "2024-01-01"},
    )
    assert first.status_code == 201

    second = await client.post(
        f"/api/v1/towers/{tower.id}/flats/{flat.id}/tenants",
        json={"full_name": "Second", "phone": "9111155556", "lease_start": "2024-02-01"},
    )
    assert second.status_code == 409
    assert second.json()["error_code"] == "ONE_ACTIVE_TENANT"

    from sqlalchemy import func, select

    from app.models.tenant import Tenant

    active_count = await db_session.scalar(
        select(func.count()).select_from(Tenant).where(
            Tenant.flat_id == flat.id, Tenant.is_active.is_(True)
        )
    )
    assert active_count == 1


@pytest.mark.asyncio
async def test_tenant_history_lists_active_first_then_past_by_lease_start_desc(
    client, db_session
):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    flat = await make_flat(db_session, tower_id=tower.id)
    admin = await _make_admin(db_session, tower, ["MANAGE_RESIDENTS", "VIEW_TOWER_DATA"])
    await db_session.commit()
    await _login(client, admin.email)

    t1 = await client.post(
        f"/api/v1/towers/{tower.id}/flats/{flat.id}/tenants",
        json={"full_name": "Past Tenant", "phone": "9111166667", "lease_start": "2023-01-01"},
    )
    t1_id = t1.json()["id"]
    await client.post(
        f"/api/v1/towers/{tower.id}/flats/{flat.id}/tenants/{t1_id}/vacate",
        json={"vacated_date": "2023-12-01", "occupancy_status": "vacant"},
    )
    await client.post(
        f"/api/v1/towers/{tower.id}/flats/{flat.id}/tenants",
        json={"full_name": "Current Tenant", "phone": "9111177778", "lease_start": "2024-01-01"},
    )

    resp = await client.get(f"/api/v1/towers/{tower.id}/flats/{flat.id}/tenants")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 2
    assert items[0]["full_name"] == "Current Tenant"
    assert items[0]["is_active"] is True
    assert items[1]["full_name"] == "Past Tenant"
    assert items[1]["is_active"] is False


    # See tests/integration/test_tenant_concurrency.py for the two-concurrent-requests race
    # test — it needs two genuinely independent DB connections (see that file's docstring for
    # why this file's shared `db_session`/`client` fixtures can't exercise real row-lock
    # contention).
