from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.pagination import Pagination, pagination_params
from app.db.session import get_db
from app.models.flat import Flat
from app.models.flat_ownership import FlatOwnership
from app.models.owner import Owner
from app.models.user import User
from app.schemas.common import PageEnvelope
from app.schemas.flat import FlatOut
from app.services.flat import build_flat_out

router = APIRouter(prefix="/me", tags=["me"])


@router.get("/flats", response_model=PageEnvelope[FlatOut])
async def list_my_flats(
    pagination: Pagination = Depends(pagination_params),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PageEnvelope[FlatOut]:
    """Cross-tower list of flats where the caller is a *current* (`date_to IS NULL`) owner —
    feeds the owner dashboard/tower-switcher (Module 5 UI, this module's data). `Owner`/
    `FlatOwnership` are deliberately not tower-scoped tables (see
    `specs/02-flat-owner-tenant/overview.md`), so this route is the only place an owner's
    flats are ever listed across towers in one call.
    """
    owner_id: UUID | None = await db.scalar(
        select(Owner.id).where(Owner.user_id == current_user.id)
    )
    if owner_id is None:
        return PageEnvelope(items=[], page=pagination.page, page_size=pagination.page_size, total=0)

    base_query = (
        select(Flat)
        .join(FlatOwnership, FlatOwnership.flat_id == Flat.id)
        .where(FlatOwnership.owner_id == owner_id, FlatOwnership.date_to.is_(None))
    )
    total = await db.scalar(
        select(func.count()).select_from(base_query.with_only_columns(Flat.id).subquery())
    )
    rows = (
        (
            await db.execute(
                base_query.order_by(Flat.flat_number.asc())
                .offset(pagination.offset)
                .limit(pagination.page_size)
            )
        )
        .scalars()
        .all()
    )
    items = [await build_flat_out(db, r) for r in rows]
    return PageEnvelope(
        items=items, page=pagination.page, page_size=pagination.page_size, total=total or 0
    )
