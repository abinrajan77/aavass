"""Flat Owner (`MANAGE_OWN_FLAT`-tier) access boundary tests —
`specs/02-flat-owner-tenant/backend.md` integration test plan: an owner token can self-serve
tenant add/update/vacate on their own flat but can never edit admin-only flat fields, and can
never act on a flat they don't currently own (403/404 on every route, never leaking existence).
"""

import pytest

from tests.factories import (
    DEFAULT_PASSWORD,
    make_complex,
    make_flat,
    make_flat_ownership,
    make_owner,
    make_tower,
    make_user,
)


async def _login(client, email, password=DEFAULT_PASSWORD):
    return await client.post("/api/v1/auth/login", json={"email": email, "password": password})


async def _make_flat_owner(db_session, *, flat, email):
    user = await make_user(db_session, email=email, account_type="flat_owner")
    owner = await make_owner(db_session, full_name="Owner Self", user_id=user.id)
    await make_flat_ownership(
        db_session, flat_id=flat.id, owner_id=owner.id, created_by_user_id=user.id
    )
    await db_session.commit()
    return user, owner


@pytest.mark.asyncio
async def test_owner_cannot_edit_carpet_area_but_can_add_tenant_on_own_flat(client, db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    flat = await make_flat(db_session, tower_id=tower.id, carpet_area_sqft="800.00")
    await db_session.commit()
    owner_user, _owner = await _make_flat_owner(
        db_session, flat=flat, email="self-serve-owner@example.com"
    )

    await _login(client, owner_user.email)

    put_resp = await client.put(
        f"/api/v1/towers/{tower.id}/flats/{flat.id}", json={"carpet_area_sqft": "999.00"}
    )
    assert put_resp.status_code == 403

    get_resp = await client.get(f"/api/v1/towers/{tower.id}/flats/{flat.id}")
    assert get_resp.status_code == 200
    assert str(get_resp.json()["carpet_area_sqft"]) == "800.00"

    tenant_resp = await client.post(
        f"/api/v1/towers/{tower.id}/flats/{flat.id}/tenants",
        json={
            "full_name": "Owner-Added Tenant",
            "phone": "9445566001",
            "lease_start": "2024-01-01",
        },
    )
    assert tenant_resp.status_code == 201


@pytest.mark.asyncio
async def test_owner_can_vacate_their_own_tenant(client, db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    flat = await make_flat(db_session, tower_id=tower.id)
    await db_session.commit()
    owner_user, _owner = await _make_flat_owner(
        db_session, flat=flat, email="vacate-owner@example.com"
    )
    await _login(client, owner_user.email)

    create_resp = await client.post(
        f"/api/v1/towers/{tower.id}/flats/{flat.id}/tenants",
        json={"full_name": "Owner Tenant", "phone": "9445566002", "lease_start": "2024-01-01"},
    )
    assert create_resp.status_code == 201
    tenant_id = create_resp.json()["id"]

    vacate_resp = await client.post(
        f"/api/v1/towers/{tower.id}/flats/{flat.id}/tenants/{tenant_id}/vacate",
        json={"vacated_date": "2024-06-01", "occupancy_status": "owner_occupied"},
    )
    assert vacate_resp.status_code == 200


@pytest.mark.asyncio
async def test_owner_can_patch_their_own_tenant_record(client, db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    flat = await make_flat(db_session, tower_id=tower.id)
    await db_session.commit()
    owner_user, _owner = await _make_flat_owner(
        db_session, flat=flat, email="patch-tenant-owner@example.com"
    )
    await _login(client, owner_user.email)

    create_resp = await client.post(
        f"/api/v1/towers/{tower.id}/flats/{flat.id}/tenants",
        json={"full_name": "Patchable Tenant", "phone": "9445566010", "lease_start": "2024-01-01"},
    )
    tenant_id = create_resp.json()["id"]

    patch_resp = await client.patch(
        f"/api/v1/towers/{tower.id}/flats/{flat.id}/tenants/{tenant_id}",
        json={"phone": "9445566099"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["phone"] == "9445566099"


@pytest.mark.asyncio
async def test_owner_token_cannot_access_a_flat_they_do_not_own(client, db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    my_flat = await make_flat(db_session, tower_id=tower.id, flat_number="OWN-1")
    other_flat = await make_flat(db_session, tower_id=tower.id, flat_number="OTHER-1")
    await db_session.commit()
    owner_user, _owner = await _make_flat_owner(
        db_session, flat=my_flat, email="isolated-owner@example.com"
    )
    await _login(client, owner_user.email)

    get_resp = await client.get(f"/api/v1/towers/{tower.id}/flats/{other_flat.id}")
    assert get_resp.status_code in (403, 404)

    owners_resp = await client.get(f"/api/v1/towers/{tower.id}/flats/{other_flat.id}/owners")
    assert owners_resp.status_code in (403, 404)

    tenants_resp = await client.get(f"/api/v1/towers/{tower.id}/flats/{other_flat.id}/tenants")
    assert tenants_resp.status_code in (403, 404)

    create_tenant_resp = await client.post(
        f"/api/v1/towers/{tower.id}/flats/{other_flat.id}/tenants",
        json={"full_name": "Intruder Tenant", "phone": "9445566003", "lease_start": "2024-01-01"},
    )
    assert create_tenant_resp.status_code in (403, 404)
