import pytest

from app.core.permissions import PERMISSION_CATALOG
from tests.factories import DEFAULT_PASSWORD, make_user


async def _login(client, email, password=DEFAULT_PASSWORD):
    return await client.post("/api/v1/auth/login", json={"email": email, "password": password})


@pytest.mark.asyncio
async def test_superuser_bootstrap_creates_tower_with_admin_role_holding_all_permissions(
    client, db_session
):
    superuser = await make_user(db_session, email="super@aavaas.internal", is_superuser=True)
    await db_session.commit()

    login_resp = await _login(client, superuser.email)
    assert login_resp.status_code == 200

    complex_resp = await client.post(
        "/api/v1/complexes", json={"name": "Bootstrap Complex", "address": "1 Main St"}
    )
    assert complex_resp.status_code == 201
    complex_id = complex_resp.json()["id"]

    tower_resp = await client.post(
        f"/api/v1/complexes/{complex_id}/towers",
        json={
            "name": "Oak Tower",
            "total_floors": 12,
            "total_flats": 48,
            "association_name": "Oak Owners Association",
        },
    )
    assert tower_resp.status_code == 201
    tower_id = tower_resp.json()["id"]

    roles_resp = await client.get(f"/api/v1/towers/{tower_id}/roles")
    assert roles_resp.status_code == 200
    roles = roles_resp.json()["items"]
    admin_roles = [r for r in roles if r["is_system_default"]]
    assert len(admin_roles) == 1
    admin_role = admin_roles[0]
    assert admin_role["name"] == "Admin"
    assert sorted(admin_role["permission_codes"]) == sorted(code for code, _ in PERMISSION_CATALOG)


@pytest.mark.asyncio
async def test_non_superuser_gets_403_on_complex_and_tower_creation(client, db_session):
    regular_user = await make_user(db_session, email="not-super@example.com")
    await db_session.commit()

    login_resp = await _login(client, regular_user.email)
    assert login_resp.status_code == 200

    complex_resp = await client.post(
        "/api/v1/complexes", json={"name": "Should Fail", "address": "nowhere"}
    )
    assert complex_resp.status_code == 403

    fake_complex_id = "00000000-0000-0000-0000-000000000000"
    tower_resp = await client.post(
        f"/api/v1/complexes/{fake_complex_id}/towers",
        json={
            "name": "Nope Tower",
            "total_floors": 1,
            "total_flats": 1,
            "association_name": "Nope",
        },
    )
    assert tower_resp.status_code == 403
