"""Module 3's read surface onto Module 2's Flat/Owner/Tenant/FlatOwnership models
(`count_active`, `list_active_flat_ids`, `get_flat_read_model`) — kept as a thin translation
layer so `app.services.billing_cycle` depends only on the `FlatRead`/`OwnerRead`/`TenantRead`
dataclasses below, never on Module 2's ORM models directly. Module 2 owns `Flat`/`Owner`/
`Tenant`/`FlatOwnership` for real (`specs/02-flat-owner-tenant`); "active" here means
`deactivated_at IS NULL` (soft-delete, not a boolean flag), and "primary owner" is read via
`FlatOwnership` (`date_to IS NULL AND is_primary_contact`) since `Owner` is not itself
flat-scoped — an owner can hold multiple flats across towers (PRD §6.2.2).
"""

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.flat import Flat
from app.models.flat_ownership import FlatOwnership
from app.models.owner import Owner
from app.models.tenant import Tenant


@dataclass(frozen=True)
class TenantRead:
    id: UUID
    full_name: str


@dataclass(frozen=True)
class OwnerRead:
    id: UUID
    full_name: str


@dataclass(frozen=True)
class FlatRead:
    id: UUID
    flat_number: str
    carpet_area: Decimal
    occupancy_status: str
    current_tenant: TenantRead | None
    primary_owner: OwnerRead | None


async def count_active(db: AsyncSession, tower_id: UUID) -> int:
    """Active-flat count for a tower — drives the sync-vs-async billing-cycle generation
    threshold in backend.md §4."""
    total = await db.scalar(
        select(func.count())
        .select_from(Flat)
        .where(Flat.tower_id == tower_id, Flat.deactivated_at.is_(None))
    )
    return total or 0


async def list_active_flat_ids(db: AsyncSession, tower_id: UUID) -> list[UUID]:
    rows = (
        (
            await db.execute(
                select(Flat.id).where(
                    Flat.tower_id == tower_id, Flat.deactivated_at.is_(None)
                )
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


async def get_flat_read_model(db: AsyncSession, flat_id: UUID) -> FlatRead | None:
    """Builds the `flat.occupancy_status` / `flat.current_tenant` / `flat.primary_owner` read
    model backend.md §5's `assign_due()` operates on."""
    flat = await db.get(Flat, flat_id)
    if flat is None:
        return None

    current_tenant: TenantRead | None = None
    if flat.occupancy_status == "tenant_occupied":
        tenant = await db.scalar(
            select(Tenant)
            .where(Tenant.flat_id == flat.id, Tenant.is_active.is_(True))
            .order_by(Tenant.created_at.desc())
            .limit(1)
        )
        if tenant is not None:
            current_tenant = TenantRead(id=tenant.id, full_name=tenant.full_name)

    primary_owner_row = await db.scalar(
        select(Owner)
        .join(FlatOwnership, FlatOwnership.owner_id == Owner.id)
        .where(
            FlatOwnership.flat_id == flat.id,
            FlatOwnership.date_to.is_(None),
            FlatOwnership.is_primary_contact.is_(True),
        )
        .limit(1)
    )
    primary_owner = (
        OwnerRead(id=primary_owner_row.id, full_name=primary_owner_row.full_name)
        if primary_owner_row is not None
        else None
    )

    return FlatRead(
        id=flat.id,
        flat_number=flat.flat_number,
        carpet_area=flat.carpet_area_sqft,
        occupancy_status=flat.occupancy_status,
        current_tenant=current_tenant,
        primary_owner=primary_owner,
    )
