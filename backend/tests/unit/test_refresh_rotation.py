import pytest
from sqlalchemy import select

from app.core.errors import AppError
from app.models.refresh_token import RefreshToken
from app.services.auth import issue_refresh_token, rotate_refresh_token
from app.services.security import hash_token
from tests.factories import make_user


@pytest.mark.asyncio
async def test_rotation_issues_new_token_and_revokes_old_one(db_session):
    user = await make_user(db_session, email="rotate@example.com")
    raw_token = await issue_refresh_token(db_session, user=user)

    _, new_raw_token = await rotate_refresh_token(
        db_session, raw_token=raw_token, user_agent=None, ip_address=None
    )

    assert new_raw_token != raw_token

    old_row = await db_session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_token))
    )
    assert old_row.revoked_at is not None


@pytest.mark.asyncio
async def test_reusing_a_rotated_token_revokes_the_entire_family(db_session):
    user = await make_user(db_session, email="reuse@example.com")
    raw_token_1 = await issue_refresh_token(db_session, user=user)

    _, raw_token_2 = await rotate_refresh_token(
        db_session, raw_token=raw_token_1, user_agent=None, ip_address=None
    )
    # raw_token_2 is now the live token; raw_token_1 is revoked (rotated).

    # Reusing the already-rotated raw_token_1 must fail with 401 and burn the family,
    # including the currently-live raw_token_2.
    with pytest.raises(AppError) as exc_info:
        await rotate_refresh_token(
            db_session, raw_token=raw_token_1, user_agent=None, ip_address=None
        )
    assert exc_info.value.status_code == 401
    assert exc_info.value.error_code == "REFRESH_TOKEN_REUSED"

    # The legitimate, still-unused raw_token_2 must now also be revoked (family kill).
    with pytest.raises(AppError) as exc_info_2:
        await rotate_refresh_token(
            db_session, raw_token=raw_token_2, user_agent=None, ip_address=None
        )
    assert exc_info_2.value.status_code == 401


@pytest.mark.asyncio
async def test_unknown_token_is_rejected(db_session):
    with pytest.raises(AppError) as exc_info:
        await rotate_refresh_token(
            db_session, raw_token="not-a-real-token", user_agent=None, ip_address=None
        )
    assert exc_info.value.status_code == 401
    assert exc_info.value.error_code == "REFRESH_TOKEN_INVALID"
