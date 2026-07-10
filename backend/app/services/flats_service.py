"""Module 2 read-service stand-in.

`specs/02-flat-owner-tenant` has not landed in this codebase yet (see `app/models/flat.py`'s
stub docstring). Module 3's backend.md says this module "reads Flat/Owner/Tenant from Module 2
via its service layer" — since that service layer doesn't exist for real, this module reads the
stub models directly here, exposing exactly the read surface Module 3 needs
(`count_active`, `get_flat_read_model`). When Module 2 ships its own `flats_service.py` /
`GET /api/v1/towers/{tower_id}/flats`, this module's imports should be repointed there instead
of deleting the read functions Module 3 depends on.
"""

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.flat import Flat
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
        .where(Flat.tower_id == tower_id, Flat.is_active.is_(True))
    )
    return total or 0


async def list_active_flat_ids(db: AsyncSession, tower_id: UUID) -> list[UUID]:
    rows = (
        (
            await db.execute(
                select(Flat.id).where(Flat.tower_id == tower_id, Flat.is_active.is_(True))
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
        select(Owner).where(Owner.flat_id == flat.id, Owner.is_primary_contact.is_(True)).limit(1)
    )
    primary_owner = (
        OwnerRead(id=primary_owner_row.id, full_name=primary_owner_row.full_name)
        if primary_owner_row is not None
        else None
    )

    return FlatRead(
        id=flat.id,
        flat_number=flat.flat_number,
        carpet_area=flat.carpet_area,
        occupancy_status=flat.occupancy_status,
        current_tenant=current_tenant,
        primary_owner=primary_owner,
    )
