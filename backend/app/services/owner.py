"""Owner business logic for the global (non-tower-scoped) `PATCH /api/v1/owners/{owner_id}`
route — `Owner` spans towers (see `app/models/owner.py`), so access can't be resolved purely
from a `tower_id` path segment the way `require_permission()` does; this resolves it from the
owner's *current* `FlatOwnership` rows instead.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.errors import AppError
from app.models.association_member import AssociationMember
from app.models.flat import Flat
from app.models.flat_ownership import FlatOwnership
from app.models.owner import Owner
from app.models.role import Role
from app.models.user import User

OwnerAccessScope = str  # "manage" | "self"


async def resolve_owner_access(
    db: AsyncSession, *, owner_id: UUID, current_user: User
) -> tuple[Owner, OwnerAccessScope]:
    owner = await db.get(Owner, owner_id)
    if owner is None:
        raise AppError(404, "OWNER_NOT_FOUND", "Owner not found.")

    if current_user.is_superuser:
        return owner, "manage"

    tower_ids = (
        (
            await db.execute(
                select(Flat.tower_id)
                .join(FlatOwnership, FlatOwnership.flat_id == Flat.id)
                .where(FlatOwnership.owner_id == owner.id, FlatOwnership.date_to.is_(None))
                .distinct()
            )
        )
        .scalars()
        .all()
    )
    if tower_ids:
        member = await db.scalar(
            select(AssociationMember)
            .where(
                AssociationMember.user_id == current_user.id,
                AssociationMember.tower_id.in_(tower_ids),
                AssociationMember.deactivated_at.is_(None),
            )
            .options(joinedload(AssociationMember.role).joinedload(Role.permissions))
        )
        if member is not None and member.role.deactivated_at is None:
            codes = {p.code for p in member.role.permissions}
            if "MANAGE_RESIDENTS" in codes:
                return owner, "manage"

    if owner.user_id is not None and owner.user_id == current_user.id:
        return owner, "self"

    raise AppError(403, "PERMISSION_DENIED", "You do not have access to this owner record.")
