"""Flat business logic: response assembly (primary owner / active tenant lookups) and the
open-dues check used by flat deactivation.
"""

from typing import cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.flat import Flat
from app.models.flat_ownership import FlatOwnership
from app.models.maintenance_due import MaintenanceDue
from app.models.owner import Owner
from app.models.special_collection import SpecialCollection
from app.models.special_collection_due import SpecialCollectionDue
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
    """Whether the flat has any Pending/Overdue maintenance or special-collection due (per
    `specs/02-flat-owner-tenant/overview.md` edge case: "Deactivating a flat that has open
    dues" → `409 OPEN_DUES_EXIST` with the count). Mirrors
    `app.services.tower.tower_has_active_financials`'s scope: special-collection dues
    belonging to a cancelled collection don't count."""
    maintenance_count = (
        await db.scalar(
            select(func.count())
            .select_from(MaintenanceDue)
            .where(
                MaintenanceDue.flat_id == flat_id,
                MaintenanceDue.status.in_(("pending", "overdue")),
            )
        )
        or 0
    )
    special_collection_count = (
        await db.scalar(
            select(func.count())
            .select_from(SpecialCollectionDue)
            .where(
                SpecialCollectionDue.flat_id == flat_id,
                SpecialCollectionDue.status.in_(("pending", "overdue")),
                SpecialCollectionDue.special_collection_id.in_(
                    select(SpecialCollection.id).where(SpecialCollection.deactivated_at.is_(None))
                ),
            )
        )
        or 0
    )
    total = maintenance_count + special_collection_count
    return total > 0, total
