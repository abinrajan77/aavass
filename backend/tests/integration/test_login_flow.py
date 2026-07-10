import time

import pytest

from tests.factories import DEFAULT_PASSWORD, make_user


@pytest.mark.asyncio
async def test_login_sets_cookies_and_returns_permissions_and_towers(client, db_session):
    from tests.factories import make_association_member, make_complex, make_role, make_tower

    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    role = await make_role(
        db_session, tower_id=tower.id, name="Admin", permission_codes=["RECORD_PAYMENT"]
    )
    user = await make_user(db_session, email="login-flow@example.com")
    await make_association_member(db_session, tower_id=tower.id, user_id=user.id, role_id=role.id)
    await db_session.commit()

    resp = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": DEFAULT_PASSWORD}
    )
    assert resp.status_code == 200
    assert "access_token" in resp.cookies
    assert "refresh_token" in resp.cookies
    body = resp.json()
    assert body["permissions"] == ["RECORD_PAYMENT"]
    assert body["towers"][0]["tower_id"] == str(tower.id)


@pytest.mark.asyncio
async def test_login_with_wrong_password_returns_generic_invalid_credentials(client, db_session):
    user = await make_user(db_session, email="wrong-pw@example.com")
    await db_session.commit()

    resp = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "totally-wrong"}
    )
    assert resp.status_code == 401
    assert resp.json()["error_code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_login_with_nonexistent_email_returns_same_generic_error(client, db_session):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "no-such-user@example.com", "password": "whatever12345"},
    )
    assert resp.status_code == 401
    assert resp.json()["error_code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_wrong_password_and_nonexistent_user_have_similar_response_latency(
    client, db_session
):
    """Basic constant-time comparison check (not full rate-limiting, which is a WAF concern
    per cloud.md) — five attempts against a real user's wrong password vs. five attempts
    against a nonexistent email should not differ by an order of magnitude, which would
    indicate the DB lookup (not the hashing step) dominates and leaks user existence."""
    user = await make_user(db_session, email="timing-user@example.com")
    await db_session.commit()

    async def _time_attempts(email: str, n: int = 5) -> float:
        start = time.perf_counter()
        for _ in range(n):
            await client.post("/api/v1/auth/login", json={"email": email, "password": "wrong"})
        return time.perf_counter() - start

    existing_user_time = await _time_attempts(user.email)
    nonexistent_time = await _time_attempts("nobody-at-all@example.com")

    slower = max(existing_user_time, nonexistent_time)
    faster = min(existing_user_time, nonexistent_time)
    assert slower < faster * 5  # generous bound; guards against gross timing leaks only


@pytest.mark.asyncio
async def test_full_login_refresh_logout_cycle(client, db_session):
    user = await make_user(db_session, email="full-cycle@example.com")
    await db_session.commit()

    login_resp = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": DEFAULT_PASSWORD}
    )
    assert login_resp.status_code == 200
    old_refresh = login_resp.cookies["refresh_token"]

    refresh_resp = await client.post("/api/v1/auth/refresh")
    assert refresh_resp.status_code == 200
    new_refresh = refresh_resp.cookies["refresh_token"]
    assert new_refresh != old_refresh

    from sqlalchemy import select

    from app.models.refresh_token import RefreshToken
    from app.services.security import hash_token

    old_row = await db_session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(old_refresh))
    )
    assert old_row.revoked_at is not None

    logout_resp = await client.post("/api/v1/auth/logout")
    assert logout_resp.status_code == 204

    new_row = await db_session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(new_refresh))
    )
    assert new_row.revoked_at is not None
