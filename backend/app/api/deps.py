"""Core FastAPI dependencies: `get_current_user`, `require_permission()`, `require_superuser()`.

Implements the pseudocode in `specs/01-auth-rbac-tower-setup/backend.md` exactly:
- tower access is re-derived from `AssociationMember` on every request (never trusts a
  `tower_id` claim embedded in the JWT);
- missing membership and wrong-tower membership both collapse to the same
  `403 TOWER_ACCESS_DENIED` (never a 404 — don't leak tower existence to a non-member);
- `403 PERMISSION_DENIED` for a member missing the required permission;
- `409 TOWER_INACTIVE` for mutating verbs against a deactivated tower (reads still allowed);
- `is_superuser` bypasses tower RBAC entirely.
"""

from uuid import UUID

import jwt
from fastapi import Depends, Path, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.errors import AppError
from app.db.session import get_db
from app.models.association_member import AssociationMember
from app.models.role import Role
from app.models.tower import Tower
from app.models.user import User
from app.services.security import decode_access_token

_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _is_mutating_request(request: Request) -> bool:
    return request.method.upper() in _MUTATING_METHODS


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header[7:]
    if not token:
        raise AppError(401, "NOT_AUTHENTICATED", "Authentication required.")

    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError as exc:
        raise AppError(401, "TOKEN_EXPIRED", "Access token has expired.") from exc
    except jwt.InvalidTokenError as exc:
        raise AppError(401, "TOKEN_INVALID", "Access token is invalid.") from exc

    user_id = payload.get("sub")
    if not user_id:
        raise AppError(401, "TOKEN_INVALID", "Access token is invalid.")

    user = await db.get(User, UUID(user_id))
    if user is None or not user.is_active:
        raise AppError(401, "TOKEN_INVALID", "Access token is invalid.")
    return user


async def require_superuser(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_superuser:
        raise AppError(403, "PERMISSION_DENIED", "Superuser access required.")
    return current_user


def require_permission(permission_code: str):
    async def dependency(
        request: Request,
        tower_id: UUID = Path(...),
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> AssociationMember | None:
        if current_user.is_superuser:
            # Superuser bypasses tower RBAC entirely (platform ops only).
            return None

        member = await db.scalar(
            select(AssociationMember)
            .where(
                AssociationMember.user_id == current_user.id,
                AssociationMember.tower_id == tower_id,
                AssociationMember.deactivated_at.is_(None),
            )
            .options(joinedload(AssociationMember.role).joinedload(Role.permissions))
        )
        if member is None:
            # Covers both "no membership at all" and "cross-tower access attempt" —
            # collapsed to the same response so tower existence is never leaked.
            raise AppError(403, "TOWER_ACCESS_DENIED", "You do not have access to this tower.")

        if member.role.deactivated_at is not None:
            raise AppError(403, "ROLE_INACTIVE", "Your role has been deactivated.")

        granted_codes = {p.code for p in member.role.permissions}
        if permission_code not in granted_codes:
            raise AppError(
                403, "PERMISSION_DENIED", f"Missing required permission: {permission_code}."
            )

        tower = await db.get(Tower, tower_id)
        if tower is None:
            raise AppError(403, "TOWER_ACCESS_DENIED", "You do not have access to this tower.")
        if tower.deactivated_at is not None and _is_mutating_request(request):
            raise AppError(409, "TOWER_INACTIVE", "This tower has been deactivated.")

        return member

    return dependency
