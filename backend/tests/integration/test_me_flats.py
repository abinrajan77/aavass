"""`GET /api/v1/me/flats` — cross-tower list of flats where the caller is a current owner
(`specs/02-flat-owner-tenant/backend.md` routes table)."""

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


@pytest.mark.asyncio
async def test_me_flats_lists_owned_flats_across_towers(client, db_session):
    complex_row = await make_complex(db_session)
    tower_a = await make_tower(db_session, complex_id=complex_row.id, name="Tower MF-A", code="MFA")
    tower_b = await make_tower(db_session, complex_id=complex_row.id, name="Tower MF-B", code="MFB")
    flat_a = await make_flat(db_session, tower_id=tower_a.id, flat_number="A1")
    flat_b = await make_flat(db_session, tower_id=tower_b.id, flat_number="B1")
    unrelated_flat = await make_flat(db_session, tower_id=tower_a.id, flat_number="A2")

    owner_user = await make_user(
        db_session, email="cross-tower-owner@example.com", account_type="flat_owner"
    )
    owner = await make_owner(db_session, full_name="Cross Tower Owner", user_id=owner_user.id)
    await make_flat_ownership(
        db_session, flat_id=flat_a.id, owner_id=owner.id, created_by_user_id=owner_user.id
    )
    await make_flat_ownership(
        db_session, flat_id=flat_b.id, owner_id=owner.id, created_by_user_id=owner_user.id
    )
    # Ownership that has ended must not show up.
    other_owner = await make_owner(db_session, full_name="Ex Owner", user_id=None)
    await make_flat_ownership(
        db_session,
        flat_id=unrelated_flat.id,
        owner_id=other_owner.id,
        created_by_user_id=owner_user.id,
    )
    await db_session.commit()

    await _login(client, owner_user.email)
    resp = await client.get("/api/v1/me/flats")
    assert resp.status_code == 200
    flat_ids = {item["id"] for item in resp.json()["items"]}
    assert flat_ids == {str(flat_a.id), str(flat_b.id)}


@pytest.mark.asyncio
async def test_me_flats_empty_for_user_with_no_owner_record(client, db_session):
    user = await make_user(db_session, email="no-owner-record@example.com")
    await db_session.commit()
    await _login(client, user.email)

    resp = await client.get("/api/v1/me/flats")
    assert resp.status_code == 200
    assert resp.json()["items"] == []
    assert resp.json()["total"] == 0
