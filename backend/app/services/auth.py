"""Login, refresh-rotation, logout, and forgot/reset-password business logic.

Refresh tokens are opaque 256-bit random values, stored only as a SHA-256 hash (per
`cloud.md`). Rotation is single-use: every `/auth/refresh` call issues a brand-new token and
immediately revokes the one presented. Tokens are chained via `family_id`; if a
already-revoked token is presented again (theft/replay), the *entire* family is revoked and
the caller must re-authenticate from scratch.
"""

import uuid
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.association_member import AssociationMember
from app.models.password_reset_token import PasswordResetToken
from app.models.permission import Permission
from app.models.refresh_token import RefreshToken
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.tower import Tower
from app.models.user import User
from app.services.security import (
    generate_opaque_token,
    hash_password,
    hash_token,
    password_reset_token_expiry,
    refresh_token_expiry,
    verify_password,
)


async def authenticate_user(db: AsyncSession, *, email: str, password: str) -> User:
    user = await db.scalar(select(User).where(User.email == email))
    # Always run the hasher even on a missing user, using a fixed dummy hash, so a timing
    # side-channel can't distinguish "no such user" from "wrong password" (no user-enumeration).
    dummy_hash = (
        "$argon2id$v=19$m=65536,t=3,p=4$"
        "c29tZXNhbHRzb21lc2FsdA$ZmFrZWhhc2hmYWtlaGFzaGZha2VoYXNoZmFrZQ"
    )
    hashed = user.hashed_password if user else dummy_hash
    password_ok = verify_password(password, hashed)

    if not user or not user.is_active or not password_ok:
        raise AppError(401, "INVALID_CREDENTIALS", "Incorrect email or password.")

    user.last_login_at = datetime.now(UTC)
    return user


async def get_user_permissions_and_towers(
    db: AsyncSession, user: User
) -> tuple[list[str], list[dict]]:
    if user.is_superuser:
        return [], []

    members = (
        (
            await db.execute(
                select(AssociationMember).where(
                    AssociationMember.user_id == user.id,
                    AssociationMember.deactivated_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )

    permission_codes: set[str] = set()
    towers: list[dict] = []
    for member in members:
        role = await db.get(Role, member.role_id)
        tower = await db.get(Tower, member.tower_id)
        if role is None or tower is None or role.deactivated_at is not None:
            continue
        code_rows = await db.execute(
            select(Permission.code)
            .join(RolePermission, Permission.id == RolePermission.permission_id)
            .where(RolePermission.role_id == role.id)
        )
        role_codes = code_rows.scalars().all()
        permission_codes.update(role_codes)
        towers.append({"tower_id": tower.id, "tower_name": tower.name, "role_name": role.name})

    return sorted(permission_codes), towers


async def issue_refresh_token(
    db: AsyncSession,
    *,
    user: User,
    family_id: UUID | None = None,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> str:
    raw_token = generate_opaque_token()
    row = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        family_id=family_id or uuid.uuid4(),
        user_agent=user_agent,
        ip_address=ip_address,
        expires_at=refresh_token_expiry(),
    )
    db.add(row)
    await db.flush()
    return raw_token


async def rotate_refresh_token(
    db: AsyncSession, *, raw_token: str, user_agent: str | None, ip_address: str | None
) -> tuple[User, str]:
    token_hash = hash_token(raw_token)
    token_row = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))

    if token_row is None:
        raise AppError(401, "REFRESH_TOKEN_INVALID", "Refresh token is invalid.")

    if token_row.revoked_at is not None:
        # Reuse of an already-rotated (single-use) token — theft/replay signal.
        # Revoke the entire token family so all descendant sessions are killed.
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == token_row.family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        raise AppError(
            401, "REFRESH_TOKEN_REUSED", "Refresh token reuse detected; session revoked."
        )

    if token_row.expires_at < datetime.now(UTC):
        raise AppError(401, "REFRESH_TOKEN_EXPIRED", "Refresh token has expired.")

    user = await db.get(User, token_row.user_id)
    if user is None or not user.is_active:
        raise AppError(401, "REFRESH_TOKEN_INVALID", "Refresh token is invalid.")

    token_row.revoked_at = datetime.now(UTC)
    new_raw_token = await issue_refresh_token(
        db,
        user=user,
        family_id=token_row.family_id,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    return user, new_raw_token


async def revoke_refresh_token(db: AsyncSession, *, raw_token: str) -> None:
    token_hash = hash_token(raw_token)
    token_row = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    if token_row is not None and token_row.revoked_at is None:
        token_row.revoked_at = datetime.now(UTC)


async def revoke_all_user_refresh_tokens(db: AsyncSession, *, user_id: UUID) -> None:
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )


async def create_password_reset_token(db: AsyncSession, *, user: User) -> str:
    raw_token = generate_opaque_token()
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(raw_token),
            expires_at=password_reset_token_expiry(),
        )
    )
    await db.flush()
    return raw_token


async def reset_password(db: AsyncSession, *, raw_token: str, new_password: str) -> User:
    token_hash = hash_token(raw_token)
    token_row = await db.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    )
    if (
        token_row is None
        or token_row.used_at is not None
        or token_row.expires_at < datetime.now(UTC)
    ):
        raise AppError(
            400, "RESET_TOKEN_INVALID", "This password reset link is invalid or has expired."
        )

    user = await db.get(User, token_row.user_id)
    if user is None:
        raise AppError(
            400, "RESET_TOKEN_INVALID", "This password reset link is invalid or has expired."
        )

    user.hashed_password = hash_password(new_password)
    user.force_password_change = False
    token_row.used_at = datetime.now(UTC)
    await revoke_all_user_refresh_tokens(db, user_id=user.id)
    return user
