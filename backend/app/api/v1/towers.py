from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_permission, require_superuser
from app.core.errors import AppError
from app.core.pagination import Pagination, pagination_params
from app.db.session import get_db
from app.models.apartment_complex import ApartmentComplex
from app.models.tower import Tower
from app.models.user import User
from app.schemas.common import PageEnvelope
from app.schemas.tower import CreateTowerRequest, TowerOut, UpdateTowerRequest
from app.services.audit import write_audit_log
from app.services.tower import (
    derive_unique_tower_code,
    seed_admin_role,
    tower_has_active_financials,
)

router = APIRouter(tags=["towers"])


@router.post(
    "/complexes/{complex_id}/towers",
    response_model=TowerOut,
    status_code=201,
    dependencies=[Depends(require_superuser)],
)
async def create_tower(
    complex_id: UUID,
    payload: CreateTowerRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TowerOut:
    complex_row = await db.get(ApartmentComplex, complex_id)
    if complex_row is None:
        raise AppError(404, "COMPLEX_NOT_FOUND", "Complex not found.")

    code = await derive_unique_tower_code(db, name=payload.name, requested_code=payload.code)
    tower = Tower(
        complex_id=complex_id,
        name=payload.name,
        code=code,
        total_floors=payload.total_floors,
        total_flats=payload.total_flats,
        association_name=payload.association_name,
    )
    db.add(tower)
    await db.flush()

    await seed_admin_role(db, tower_id=tower.id)

    await write_audit_log(
        db,
        actor=current_user,
        tower_id=tower.id,
        action="TOWER_CREATED",
        entity_type="Tower",
        entity_id=tower.id,
        before=None,
        after={"name": tower.name, "code": tower.code},
    )
    await db.commit()
    await db.refresh(tower)
    return TowerOut.model_validate(tower)


@router.get(
    "/complexes/{complex_id}/towers",
    response_model=PageEnvelope[TowerOut],
    dependencies=[Depends(require_superuser)],
)
async def list_towers_for_complex(
    complex_id: UUID,
    pagination: Pagination = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
) -> PageEnvelope[TowerOut]:
    total = await db.scalar(
        select(func.count()).select_from(Tower).where(Tower.complex_id == complex_id)
    )
    rows = (
        (
            await db.execute(
                select(Tower)
                .where(Tower.complex_id == complex_id)
                .order_by(Tower.created_at.desc())
                .offset(pagination.offset)
                .limit(pagination.page_size)
            )
        )
        .scalars()
        .all()
    )
    return PageEnvelope(
        items=[TowerOut.model_validate(r) for r in rows],
        page=pagination.page,
        page_size=pagination.page_size,
        total=total or 0,
    )


@router.get("/towers/{tower_id}", response_model=TowerOut)
async def get_tower(
    tower_id: UUID,
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("VIEW_TOWER_DATA")),
) -> TowerOut:
    tower = await db.get(Tower, tower_id)
    if tower is None:
        raise AppError(403, "TOWER_ACCESS_DENIED", "You do not have access to this tower.")
    return TowerOut.model_validate(tower)


@router.put("/towers/{tower_id}", response_model=TowerOut)
async def update_tower(
    tower_id: UUID,
    payload: UpdateTowerRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("MANAGE_COMPLEX")),
) -> TowerOut:
    tower = await db.get(Tower, tower_id)
    if tower is None:
        raise AppError(403, "TOWER_ACCESS_DENIED", "You do not have access to this tower.")

    before = {
        "name": tower.name,
        "total_floors": tower.total_floors,
        "total_flats": tower.total_flats,
        "association_name": tower.association_name,
    }
    if payload.name is not None:
        tower.name = payload.name
    if payload.total_floors is not None:
        tower.total_floors = payload.total_floors
    if payload.total_flats is not None:
        tower.total_flats = payload.total_flats
    if payload.association_name is not None:
        tower.association_name = payload.association_name
    after = {
        "name": tower.name,
        "total_floors": tower.total_floors,
        "total_flats": tower.total_flats,
        "association_name": tower.association_name,
    }

    await write_audit_log(
        db,
        actor=current_user,
        tower_id=tower.id,
        action="TOWER_UPDATED",
        entity_type="Tower",
        entity_id=tower.id,
        before=before,
        after=after,
    )
    await db.commit()
    await db.refresh(tower)
    return TowerOut.model_validate(tower)


@router.post("/towers/{tower_id}/deactivate", response_model=TowerOut)
async def deactivate_tower(
    tower_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("MANAGE_COMPLEX")),
) -> TowerOut:
    tower = await db.get(Tower, tower_id)
    if tower is None:
        raise AppError(403, "TOWER_ACCESS_DENIED", "You do not have access to this tower.")

    if await tower_has_active_financials(db, tower_id=tower_id):
        raise AppError(
            409,
            "TOWER_HAS_ACTIVE_FINANCIALS",
            "This tower has active Pending/Overdue dues and cannot be deactivated.",
        )

    before = {"deactivated_at": None}
    tower.deactivated_at = datetime.now(UTC)
    after = {"deactivated_at": tower.deactivated_at.isoformat()}

    await write_audit_log(
        db,
        actor=current_user,
        tower_id=tower.id,
        action="TOWER_DEACTIVATED",
        entity_type="Tower",
        entity_id=tower.id,
        before=before,
        after=after,
    )
    await db.commit()
    await db.refresh(tower)
    return TowerOut.model_validate(tower)


@router.post(
    "/towers/{tower_id}/reactivate",
    response_model=TowerOut,
    dependencies=[Depends(require_superuser)],
)
async def reactivate_tower(
    tower_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TowerOut:
    tower = await db.get(Tower, tower_id)
    if tower is None:
        raise AppError(404, "TOWER_NOT_FOUND", "Tower not found.")

    before = {"deactivated_at": tower.deactivated_at.isoformat() if tower.deactivated_at else None}
    tower.deactivated_at = None
    after = {"deactivated_at": None}

    await write_audit_log(
        db,
        actor=current_user,
        tower_id=tower.id,
        action="TOWER_REACTIVATED",
        entity_type="Tower",
        entity_id=tower.id,
        before=before,
        after=after,
    )
    await db.commit()
    await db.refresh(tower)
    return TowerOut.model_validate(tower)
