"""Owner self-service portal auth dependencies (backend.md §3), parallel to `deps_flat.py`
(Module 2) but scoped to `/api/v1/owners/me/...` routes with no `tower_id` path param at all
(`flats-summary`) or only `flat_id` (`dashboard`) — never `require_permission()`, since flat
owners aren't `association_members`/role-based (`00-architecture-and-standards.md` §5.2); they
authenticate as `User(account_type="flat_owner")` linked via `Owner.user_id` and are scoped by
`FlatOwnership` rows.

`require_owned_flat` re-validates the caller's **active** (`date_to IS NULL`) `FlatOwnership`
for the requested `flat_id` on every request — collapsing "never owned", "owned but sold
(`date_to` set)", and "flat belongs to someone else" all to the same `403 OWNERSHIP_NOT_FOUND`,
never a `404` (overview.md acceptance criterion 7: don't leak whether the flat exists to a
caller who isn't currently party to it).
"""

from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.errors import AppError
from app.db.session import get_db
from app.models.flat import Flat
from app.models.flat_ownership import FlatOwnership
from app.models.owner import Owner
from app.models.user import User


async def require_owner(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Owner:
    """Resolves the caller's `Owner` record — `403 NOT_A_FLAT_OWNER` (defensive: should not
    normally be reachable by a `tower_admin` account, but a superuser/tower-admin user with no
    linked `Owner` row must not fall through to a 500) if this account isn't linked to one."""
    owner = await db.scalar(select(Owner).where(Owner.user_id == current_user.id))
    if owner is None:
        raise AppError(
            403, "NOT_A_FLAT_OWNER", "This account is not linked to any flat ownership."
        )
    return owner


@dataclass(frozen=True)
class OwnedFlatAccess:
    owner: Owner
    flat: Flat


async def require_owned_flat(
    flat_id: UUID = Path(...),
    owner: Owner = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
) -> OwnedFlatAccess:
    ownership = await db.scalar(
        select(FlatOwnership).where(
            FlatOwnership.owner_id == owner.id,
            FlatOwnership.flat_id == flat_id,
            FlatOwnership.date_to.is_(None),
        )
    )
    if ownership is None:
        raise AppError(
            403, "OWNERSHIP_NOT_FOUND", "You do not have access to this flat."
        )
    flat = await db.get(Flat, flat_id)
    assert flat is not None, f"flat {flat_id} must exist (FK-enforced by flat_ownerships)"
    return OwnedFlatAccess(owner=owner, flat=flat)
