"""Flat business logic: response assembly (primary owner / active tenant lookups) and the
(stubbed) open-dues check used by flat deactivation.
"""

from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.flat import Flat
from app.models.flat_ownership import FlatOwnership
from app.models.owner import Owner
from app.models.tenant import Tenant
from app.schemas.flat import FlatOut, OccupancyStatus
from app.schemas.owner import OwnerSummary
from app.schemas.tenant import TenantSummary


async def get_primary_owner(db: AsyncSession, *, flat_id: UUID) -> Owner | None:
    return await db.scalar(
        select(Owner)
        .join(FlatOwnership, FlatOwnership.owner_id == Owner.id)
        .where(
            FlatOwnership.flat_id == flat_id,
            FlatOwnership.date_to.is_(None),
            FlatOwnership.is_primary_contact.is_(True),
        )
    )


async def get_active_tenant(db: AsyncSession, *, flat_id: UUID) -> Tenant | None:
    return await db.scalar(
        select(Tenant).where(Tenant.flat_id == flat_id, Tenant.is_active.is_(True))
    )


async def build_flat_out(db: AsyncSession, flat: Flat) -> FlatOut:
    primary_owner = await get_primary_owner(db, flat_id=flat.id)
    active_tenant = await get_active_tenant(db, flat_id=flat.id)
    return FlatOut(
        id=flat.id,
        tower_id=flat.tower_id,
        flat_number=flat.flat_number,
        floor=flat.floor,
        type=flat.type,
        carpet_area_sqft=flat.carpet_area_sqft,
        occupancy_status=cast(OccupancyStatus, flat.occupancy_status),
        primary_owner=OwnerSummary.model_validate(primary_owner) if primary_owner else None,
        active_tenant=TenantSummary.model_validate(active_tenant) if active_tenant else None,
        deactivated_at=flat.deactivated_at,
        created_at=flat.created_at,
        updated_at=flat.updated_at,
    )


async def flat_has_open_dues(db: AsyncSession, *, flat_id: UUID) -> tuple[bool, int]:
    """Whether the flat has any Pending/Overdue maintenance or special-collection due.

    TODO(module-3/4): Modules 3 (Maintenance Billing) and 4 (Special Collections &
    Expenditure) own the `maintenance_dues` / `special_collection_dues` tables this check
    needs to query (per `specs/02-flat-owner-tenant/overview.md` edge case: "Deactivating a
    flat that has open dues" → `409 OPEN_DUES_EXIST` with the count). Those tables don't
    exist yet in this codebase (mirrors the identical stub already shipped for towers in
    `app/services/tower.py::tower_has_active_financials`), so this stub always reports "no
    open dues found" (i.e. deactivation is never blocked by this specific check). Replace this
    function body with a real query against `maintenance_dues`/`special_collection_dues`
    (status IN ('pending', 'overdue') AND flat_id = :flat_id) once Module 3/4 land — do not
    fake the whole feature by hardcoding a block, only the missing data dependency is stubbed.
    """
    return False, 0
