import pytest

from tests.factories import DEFAULT_PASSWORD, make_user


@pytest.mark.asyncio
async def test_healthz_returns_ok_when_db_reachable(client):
    resp = await client.get("/api/v1/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_me_requires_authentication(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_current_user_after_login(client, db_session):
    user = await make_user(db_session, email="me-endpoint@example.com")
    await db_session.commit()

    await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": DEFAULT_PASSWORD}
    )
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    assert resp.json()["user"]["email"] == user.email
