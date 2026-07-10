"""Flat/Owner/Tenant access dependencies (Module 2).

`require_permission()` in `app/api/deps.py` (Module 1) resolves access via an
`AssociationMember` row and is reused as-is for admin-only routes (flat CRUD, ownership
management). It does not, however, cover Flat Owners: they authenticate as
`User(account_type="flat_owner")` linked via `Owner.user_id` and are scoped by `FlatOwnership`
rows, not `AssociationMember` rows (`specs/02-flat-owner-tenant/overview.md` "Owner linked to
flats across multiple towers"). This module layers that flat-owner (`MANAGE_OWN_FLAT`-tier)
access on top of the existing admin path, for the handful of routes PRD §6.2.3/§6.6 let owners
self-serve (flat/owners/tenants reads, tenant add/update/vacate on their own flat) — without
touching `app/api/deps.py` itself.
"""

from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, Path, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.deps import get_current_user
from app.core.errors import AppError
from app.db.session import get_db
from app.models.association_member import AssociationMember
from app.models.flat import Flat
from app.models.flat_ownership import FlatOwnership
from app.models.owner import Owner
from app.models.role import Role
from app.models.tower import Tower
from app.models.user import User

_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


@dataclass
class FlatAccess:
    flat: Flat
    scope: str  # "admin" | "owner"
    member: AssociationMember | None = None
    owner: Owner | None = None


async def _load_flat(db: AsyncSession, *, tower_id: UUID, flat_id: UUID) -> Flat:
    flat = await db.scalar(select(Flat).where(Flat.id == flat_id, Flat.tower_id == tower_id))
    if flat is None:
        raise AppError(404, "FLAT_NOT_FOUND", "Flat not found.")
    return flat


def require_flat_access(*, manage: bool):
    """Dependency factory for routes nested under `/towers/{tower_id}/flats/{flat_id}`.

    `manage=True`: admin needs `MANAGE_RESIDENTS`; the flat's own current owner is also let
    through (tenant add/update/vacate on their own flat).
    `manage=False`: admin needs `VIEW_TOWER_DATA` (or `MANAGE_RESIDENTS`); the flat's own
    current owner is also let through (read-only routes).
    """

    async def dependency(
        request: Request,
        tower_id: UUID = Path(...),
        flat_id: UUID = Path(...),
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> FlatAccess:
        if current_user.is_superuser:
            flat = await _load_flat(db, tower_id=tower_id, flat_id=flat_id)
            return FlatAccess(flat=flat, scope="admin")

        member = await db.scalar(
            select(AssociationMember)
            .where(
                AssociationMember.user_id == current_user.id,
                AssociationMember.tower_id == tower_id,
                AssociationMember.deactivated_at.is_(None),
            )
            .options(joinedload(AssociationMember.role).joinedload(Role.permissions))
        )
        if member is not None:
            if member.role.deactivated_at is not None:
                raise AppError(403, "ROLE_INACTIVE", "Your role has been deactivated.")
            codes = {p.code for p in member.role.permissions}
            required = "MANAGE_RESIDENTS" if manage else "VIEW_TOWER_DATA"
            if required not in codes and "MANAGE_RESIDENTS" not in codes:
                raise AppError(
                    403, "PERMISSION_DENIED", f"Missing required permission: {required}."
                )
            tower = await db.get(Tower, tower_id)
            if tower is None:
                raise AppError(
                    403, "TOWER_ACCESS_DENIED", "You do not have access to this tower."
                )
            if tower.deactivated_at is not None and request.method.upper() in _MUTATING_METHODS:
                raise AppError(409, "TOWER_INACTIVE", "This tower has been deactivated.")
            flat = await _load_flat(db, tower_id=tower_id, flat_id=flat_id)
            return FlatAccess(flat=flat, scope="admin", member=member)

        # Not an association member of this tower — fall back to flat-owner scope. Collapses
        # "no Owner record", "not currently linked to this flat", and "flat in a different
        # tower" all to the same 403, mirroring `require_permission()`'s "never leak existence
        # to a non-member" rule.
        owner = await db.scalar(select(Owner).where(Owner.user_id == current_user.id))
        if owner is not None:
            ownership = await db.scalar(
                select(FlatOwnership).where(
                    FlatOwnership.owner_id == owner.id,
                    FlatOwnership.flat_id == flat_id,
                    FlatOwnership.date_to.is_(None),
                )
            )
            if ownership is not None:
                flat = await _load_flat(db, tower_id=tower_id, flat_id=flat_id)
                return FlatAccess(flat=flat, scope="owner", owner=owner)

        raise AppError(403, "TOWER_ACCESS_DENIED", "You do not have access to this flat.")

    return dependency
