"""`PATCH /api/v1/owners/{owner_id}` — global (non-tower-scoped) route.
`specs/02-flat-owner-tenant/overview.md` edge case: an owner may update their own
phone/email but never full_name/id_number, even via a raw API call; a `MANAGE_RESIDENTS`
admin (resolved via the owner's active `FlatOwnership`) may edit everything.
"""

import pytest

from tests.factories import (
    DEFAULT_PASSWORD,
    make_association_member,
    make_complex,
    make_flat,
    make_flat_ownership,
    make_owner,
    make_role,
    make_tower,
    make_user,
)


async def _login(client, email, password=DEFAULT_PASSWORD):
    return await client.post("/api/v1/auth/login", json={"email": email, "password": password})


@pytest.mark.asyncio
async def test_owner_self_update_accepts_contact_fields_but_rejects_full_name(client, db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    flat = await make_flat(db_session, tower_id=tower.id)
    owner_user = await make_user(
        db_session, email="self-owner-patch@example.com", account_type="flat_owner"
    )
    owner = await make_owner(
        db_session, full_name="Original Name", phone="9000011111", user_id=owner_user.id
    )
    await make_flat_ownership(
        db_session, flat_id=flat.id, owner_id=owner.id, created_by_user_id=owner_user.id
    )
    await db_session.commit()
    await _login(client, owner_user.email)

    ok_resp = await client.patch(
        f"/api/v1/owners/{owner.id}", json={"phone": "9000022222"}
    )
    assert ok_resp.status_code == 200
    assert ok_resp.json()["phone"] == "9000022222"
    assert ok_resp.json()["full_name"] == "Original Name"

    smuggle_resp = await client.patch(
        f"/api/v1/owners/{owner.id}", json={"full_name": "Smuggled Name"}
    )
    assert smuggle_resp.status_code == 422


@pytest.mark.asyncio
async def test_admin_with_manage_residents_can_update_full_name(client, db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    flat = await make_flat(db_session, tower_id=tower.id)
    owner = await make_owner(db_session, full_name="Before Name", phone="9000033333")
    role = await make_role(
        db_session, tower_id=tower.id, name="Admin", permission_codes=["MANAGE_RESIDENTS"]
    )
    admin_user = await make_user(db_session, email="patch-admin@example.com")
    await make_association_member(
        db_session, tower_id=tower.id, user_id=admin_user.id, role_id=role.id
    )
    await make_flat_ownership(
        db_session, flat_id=flat.id, owner_id=owner.id, created_by_user_id=admin_user.id
    )
    await db_session.commit()
    await _login(client, admin_user.email)

    resp = await client.patch(
        f"/api/v1/owners/{owner.id}", json={"full_name": "After Name", "id_number": "ID-9"}
    )
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "After Name"
    assert resp.json()["id_number"] == "ID-9"


@pytest.mark.asyncio
async def test_unrelated_user_cannot_update_owner(client, db_session):
    owner = await make_owner(db_session, full_name="Private Owner", phone="9000044444")
    stranger = await make_user(db_session, email="stranger@example.com")
    await db_session.commit()
    await _login(client, stranger.email)

    resp = await client.patch(f"/api/v1/owners/{owner.id}", json={"phone": "9000055555"})
    assert resp.status_code == 403
