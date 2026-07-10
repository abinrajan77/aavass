from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.deps import get_current_user, require_permission
from app.api.deps_flat import FlatAccess, require_flat_access
from app.core.errors import AppError
from app.core.pagination import Pagination, pagination_params
from app.db.session import get_db
from app.models.flat import Flat
from app.models.flat_ownership import FlatOwnership
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.common import PageEnvelope
from app.schemas.flat import FlatCreate, FlatOut, FlatUpdate
from app.schemas.owner import (
    FlatOwnershipCreateRequest,
    FlatOwnershipOut,
    FlatOwnershipUpdate,
    OwnerRemoveRequest,
)
from app.schemas.tenant import TenantCreate, TenantOut, TenantUpdate, TenantVacate
from app.services import occupancy, ownership
from app.services.audit import write_audit_log
from app.services.flat import build_flat_out, flat_has_open_dues

router = APIRouter(prefix="/towers/{tower_id}/flats", tags=["flats"])


async def _get_flat_or_404(db: AsyncSession, *, tower_id: UUID, flat_id: UUID) -> Flat:
    flat = await db.scalar(select(Flat).where(Flat.id == flat_id, Flat.tower_id == tower_id))
    if flat is None:
        raise AppError(404, "FLAT_NOT_FOUND", "Flat not found.")
    return flat


async def _flat_number_taken(
    db: AsyncSession, *, tower_id: UUID, flat_number: str, exclude_flat_id: UUID | None = None
) -> bool:
    stmt = select(Flat).where(
        Flat.tower_id == tower_id,
        Flat.flat_number == flat_number,
        Flat.deactivated_at.is_(None),
    )
    if exclude_flat_id is not None:
        stmt = stmt.where(Flat.id != exclude_flat_id)
    return await db.scalar(stmt) is not None


# --------------------------------------------------------------------------------------------
# Flats
# --------------------------------------------------------------------------------------------


@router.get("", response_model=PageEnvelope[FlatOut])
async def list_flats(
    tower_id: UUID,
    type: Literal["1BHK", "2BHK", "3BHK", "OTHER"] | None = Query(default=None),
    occupancy_status: Literal["owner_occupied", "tenant_occupied", "vacant"] | None = Query(
        default=None
    ),
    q: str | None = Query(default=None, description="Search flat_number (contains match)"),
    pagination: Pagination = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("VIEW_TOWER_DATA")),
) -> PageEnvelope[FlatOut]:
    filters = [Flat.tower_id == tower_id]
    if type is not None:
        filters.append(Flat.type == type)
    if occupancy_status is not None:
        filters.append(Flat.occupancy_status == occupancy_status)
    if q:
        filters.append(Flat.flat_number.ilike(f"%{q}%"))

    total = await db.scalar(select(func.count()).select_from(Flat).where(*filters))
    rows = (
        (
            await db.execute(
                select(Flat)
                .where(*filters)
                .order_by(Flat.flat_number.asc())
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


@router.post("", response_model=FlatOut, status_code=201)
async def create_flat(
    tower_id: UUID,
    payload: FlatCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("MANAGE_RESIDENTS")),
) -> FlatOut:
    if await _flat_number_taken(db, tower_id=tower_id, flat_number=payload.flat_number):
        raise AppError(
            409,
            "FLAT_NUMBER_TAKEN",
            "An active flat with this number already exists in this tower.",
        )

    flat = Flat(
        tower_id=tower_id,
        flat_number=payload.flat_number,
        floor=payload.floor,
        type=payload.type,
        carpet_area_sqft=payload.carpet_area_sqft,
        occupancy_status="vacant",
    )
    db.add(flat)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise AppError(
            409,
            "FLAT_NUMBER_TAKEN",
            "An active flat with this number already exists in this tower.",
        ) from exc

    await write_audit_log(
        db,
        actor=current_user,
        tower_id=tower_id,
        action="FLAT_CREATED",
        entity_type="Flat",
        entity_id=flat.id,
        before=None,
        after={"flat_number": flat.flat_number, "type": flat.type},
    )
    await db.commit()
    await db.refresh(flat)
    return await build_flat_out(db, flat)


@router.get("/{flat_id}", response_model=FlatOut)
async def get_flat(
    tower_id: UUID,
    flat_id: UUID,
    db: AsyncSession = Depends(get_db),
    access: FlatAccess = Depends(require_flat_access(manage=False)),
) -> FlatOut:
    return await build_flat_out(db, access.flat)


@router.put("/{flat_id}", response_model=FlatOut)
async def update_flat(
    tower_id: UUID,
    flat_id: UUID,
    payload: FlatUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("MANAGE_RESIDENTS")),
) -> FlatOut:
    flat = await _get_flat_or_404(db, tower_id=tower_id, flat_id=flat_id)
    if flat.deactivated_at is not None:
        raise AppError(409, "IMMUTABLE_RECORD", "This flat has been deactivated.")

    if payload.flat_number is not None and payload.flat_number != flat.flat_number:
        if await _flat_number_taken(
            db, tower_id=tower_id, flat_number=payload.flat_number, exclude_flat_id=flat.id
        ):
            raise AppError(
                409,
                "FLAT_NUMBER_TAKEN",
                "An active flat with this number already exists in this tower.",
            )

    before = {
        "flat_number": flat.flat_number,
        "floor": flat.floor,
        "type": flat.type,
        "carpet_area_sqft": str(flat.carpet_area_sqft),
    }
    if payload.flat_number is not None:
        flat.flat_number = payload.flat_number
    if payload.floor is not None:
        flat.floor = payload.floor
    if payload.type is not None:
        flat.type = payload.type
    if payload.carpet_area_sqft is not None:
        flat.carpet_area_sqft = payload.carpet_area_sqft
    after = {
        "flat_number": flat.flat_number,
        "floor": flat.floor,
        "type": flat.type,
        "carpet_area_sqft": str(flat.carpet_area_sqft),
    }

    await write_audit_log(
        db,
        actor=current_user,
        tower_id=tower_id,
        action="FLAT_UPDATED",
        entity_type="Flat",
        entity_id=flat.id,
        before=before,
        after=after,
    )
    await db.commit()
    await db.refresh(flat)
    return await build_flat_out(db, flat)


@router.post("/{flat_id}/deactivate", response_model=FlatOut)
async def deactivate_flat(
    tower_id: UUID,
    flat_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("MANAGE_RESIDENTS")),
) -> FlatOut:
    flat = await _get_flat_or_404(db, tower_id=tower_id, flat_id=flat_id)

    has_open_dues, open_dues_count = await flat_has_open_dues(db, flat_id=flat.id)
    if has_open_dues:
        raise AppError(
            409,
            "OPEN_DUES_EXIST",
            f"This flat has {open_dues_count} open due(s); resolve/waive them before "
            "deactivating.",
            field_errors={"open_dues_count": str(open_dues_count)},
        )

    before = {"deactivated_at": None}
    flat.deactivated_at = datetime.now(UTC)
    after = {"deactivated_at": flat.deactivated_at.isoformat()}

    await write_audit_log(
        db,
        actor=current_user,
        tower_id=tower_id,
        action="FLAT_DEACTIVATED",
        entity_type="Flat",
        entity_id=flat.id,
        before=before,
        after=after,
    )
    await db.commit()
    await db.refresh(flat)
    return await build_flat_out(db, flat)


@router.post("/{flat_id}/reactivate", response_model=FlatOut)
async def reactivate_flat(
    tower_id: UUID,
    flat_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("MANAGE_RESIDENTS")),
) -> FlatOut:
    flat = await _get_flat_or_404(db, tower_id=tower_id, flat_id=flat_id)

    before = {
        "deactivated_at": flat.deactivated_at.isoformat() if flat.deactivated_at else None
    }
    flat.deactivated_at = None
    after = {"deactivated_at": None}

    await write_audit_log(
        db,
        actor=current_user,
        tower_id=tower_id,
        action="FLAT_REACTIVATED",
        entity_type="Flat",
        entity_id=flat.id,
        before=before,
        after=after,
    )
    await db.commit()
    await db.refresh(flat)
    return await build_flat_out(db, flat)


# --------------------------------------------------------------------------------------------
# Owners (FlatOwnership)
# --------------------------------------------------------------------------------------------


def _to_ownership_out(row: FlatOwnership) -> FlatOwnershipOut:
    out = FlatOwnershipOut.model_validate(row)
    return out


@router.get("/{flat_id}/owners", response_model=PageEnvelope[FlatOwnershipOut])
async def list_flat_owners(
    tower_id: UUID,
    flat_id: UUID,
    pagination: Pagination = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    access: FlatAccess = Depends(require_flat_access(manage=False)),
) -> PageEnvelope[FlatOwnershipOut]:
    total = await db.scalar(
        select(func.count()).select_from(FlatOwnership).where(FlatOwnership.flat_id == flat_id)
    )
    rows = (
        (
            await db.execute(
                select(FlatOwnership)
                .where(FlatOwnership.flat_id == flat_id)
                .options(joinedload(FlatOwnership.owner))
                .order_by(FlatOwnership.date_from.desc())
                .offset(pagination.offset)
                .limit(pagination.page_size)
            )
        )
        .scalars()
        .all()
    )
    return PageEnvelope(
        items=[_to_ownership_out(r) for r in rows],
        page=pagination.page,
        page_size=pagination.page_size,
        total=total or 0,
    )


@router.post("/{flat_id}/owners", response_model=FlatOwnershipOut, status_code=201)
async def add_flat_owner(
    tower_id: UUID,
    flat_id: UUID,
    payload: FlatOwnershipCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("MANAGE_RESIDENTS")),
) -> FlatOwnershipOut:
    flat = await _get_flat_or_404(db, tower_id=tower_id, flat_id=flat_id)
    row = await ownership.add_owner_to_flat(
        db, flat=flat, payload=payload, actor=current_user
    )
    await db.commit()
    await db.refresh(row, attribute_names=["owner"])
    return _to_ownership_out(row)


@router.patch("/{flat_id}/owners/{ownership_id}", response_model=FlatOwnershipOut)
async def update_flat_owner_primary_contact(
    tower_id: UUID,
    flat_id: UUID,
    ownership_id: UUID,
    payload: FlatOwnershipUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("MANAGE_RESIDENTS")),
) -> FlatOwnershipOut:
    flat = await _get_flat_or_404(db, tower_id=tower_id, flat_id=flat_id)
    row = await ownership.flip_primary_contact(
        db, flat=flat, ownership_id=ownership_id, payload=payload, actor=current_user
    )
    await db.commit()
    await db.refresh(row, attribute_names=["owner"])
    return _to_ownership_out(row)


@router.post("/{flat_id}/owners/{ownership_id}/remove", response_model=FlatOwnershipOut)
async def remove_flat_owner(
    tower_id: UUID,
    flat_id: UUID,
    ownership_id: UUID,
    payload: OwnerRemoveRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("MANAGE_RESIDENTS")),
) -> FlatOwnershipOut:
    flat = await _get_flat_or_404(db, tower_id=tower_id, flat_id=flat_id)
    row = await ownership.remove_owner(
        db, flat=flat, ownership_id=ownership_id, payload=payload, actor=current_user
    )
    await db.commit()
    await db.refresh(row, attribute_names=["owner"])
    return _to_ownership_out(row)


# --------------------------------------------------------------------------------------------
# Tenants
# --------------------------------------------------------------------------------------------


@router.get("/{flat_id}/tenants", response_model=PageEnvelope[TenantOut])
async def list_flat_tenants(
    tower_id: UUID,
    flat_id: UUID,
    pagination: Pagination = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    access: FlatAccess = Depends(require_flat_access(manage=False)),
) -> PageEnvelope[TenantOut]:
    total = await db.scalar(
        select(func.count()).select_from(Tenant).where(Tenant.flat_id == flat_id)
    )
    rows = (
        (
            await db.execute(
                select(Tenant)
                .where(Tenant.flat_id == flat_id)
                # Active first, then past tenants ordered by lease_start desc.
                .order_by(Tenant.is_active.desc(), Tenant.lease_start.desc())
                .offset(pagination.offset)
                .limit(pagination.page_size)
            )
        )
        .scalars()
        .all()
    )
    return PageEnvelope(
        items=[TenantOut.model_validate(r) for r in rows],
        page=pagination.page,
        page_size=pagination.page_size,
        total=total or 0,
    )


@router.post("/{flat_id}/tenants", response_model=TenantOut, status_code=201)
async def create_flat_tenant(
    tower_id: UUID,
    flat_id: UUID,
    payload: TenantCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    access: FlatAccess = Depends(require_flat_access(manage=True)),
) -> TenantOut:
    tenant = await occupancy.create_tenant(
        db, flat_id=flat_id, payload=payload, actor=current_user
    )
    await db.commit()
    await db.refresh(tenant)
    return TenantOut.model_validate(tenant)


@router.patch("/{flat_id}/tenants/{tenant_id}", response_model=TenantOut)
async def update_flat_tenant(
    tower_id: UUID,
    flat_id: UUID,
    tenant_id: UUID,
    payload: TenantUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    access: FlatAccess = Depends(require_flat_access(manage=True)),
) -> TenantOut:
    tenant = await db.scalar(
        select(Tenant).where(Tenant.id == tenant_id, Tenant.flat_id == flat_id)
    )
    if tenant is None:
        raise AppError(404, "TENANT_NOT_FOUND", "Tenant not found.")
    if not tenant.is_active:
        raise AppError(409, "IMMUTABLE_RECORD", "This tenant has already been vacated.")

    before = {"phone": tenant.phone, "email": tenant.email, "lease_end": str(tenant.lease_end)}
    if payload.phone is not None:
        tenant.phone = payload.phone
    if payload.email is not None:
        tenant.email = payload.email
    if payload.lease_end is not None:
        tenant.lease_end = payload.lease_end
    after = {"phone": tenant.phone, "email": tenant.email, "lease_end": str(tenant.lease_end)}

    await write_audit_log(
        db,
        actor=current_user,
        tower_id=access.flat.tower_id,
        action="TENANT_UPDATED",
        entity_type="Tenant",
        entity_id=tenant.id,
        before=before,
        after=after,
    )
    await db.commit()
    await db.refresh(tenant)
    return TenantOut.model_validate(tenant)


@router.post("/{flat_id}/tenants/{tenant_id}/vacate", response_model=TenantOut)
async def vacate_flat_tenant(
    tower_id: UUID,
    flat_id: UUID,
    tenant_id: UUID,
    payload: TenantVacate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    access: FlatAccess = Depends(require_flat_access(manage=True)),
) -> TenantOut:
    tenant, _flat = await occupancy.vacate_tenant(
        db, tenant_id=tenant_id, flat_id=flat_id, payload=payload, actor=current_user
    )
    await db.commit()
    await db.refresh(tenant)
    return TenantOut.model_validate(tenant)
