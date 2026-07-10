"""Occupancy auto-transition service layer — `specs/02-flat-owner-tenant/backend.md`
"Occupancy auto-transition implementation".

Implemented here (not a DB trigger) so the business logic stays in one reviewable place and
can emit the `audit_log` row in the same unit of work. Both functions row-lock the `Flat` (and,
for vacate, the `Tenant`) via `SELECT ... FOR UPDATE` so two concurrent requests against the
same flat serialize instead of racing past the "no active tenant" pre-check — the partial
unique index on `tenants(flat_id) WHERE is_active` is the second line of defense.

Neither function calls `db.commit()` — the caller commits once, in the same transaction as
the `write_audit_log()` call, per the shared audit-log contract.
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.flat import Flat
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.tenant import TenantCreate, TenantVacate
from app.services.audit import write_audit_log


async def create_tenant(
    db: AsyncSession, *, flat_id: UUID, payload: TenantCreate, actor: User
) -> Tenant:
    flat = await db.scalar(select(Flat).where(Flat.id == flat_id).with_for_update())
    if flat is None or flat.deactivated_at is not None:
        raise AppError(404, "FLAT_NOT_FOUND", "Flat not found.")

    existing_active = await db.scalar(
        select(Tenant).where(Tenant.flat_id == flat_id, Tenant.is_active.is_(True))
    )
    if existing_active is not None:
        raise AppError(
            409,
            "ONE_ACTIVE_TENANT",
            "This flat already has an active tenant; vacate the current tenant first.",
        )

    before = {"occupancy_status": flat.occupancy_status}
    tenant = Tenant(
        flat_id=flat_id,
        full_name=payload.full_name,
        phone=payload.phone,
        email=payload.email,
        id_number=payload.id_number,
        lease_start=payload.lease_start,
        lease_end=payload.lease_end,
    )
    db.add(tenant)
    flat.occupancy_status = "tenant_occupied"
    await db.flush()

    await write_audit_log(
        db,
        actor=actor,
        tower_id=flat.tower_id,
        action="TENANT_ADDED",
        entity_type="Tenant",
        entity_id=tenant.id,
        before=before,
        after={"occupancy_status": flat.occupancy_status, "tenant_id": str(tenant.id)},
    )
    return tenant


async def vacate_tenant(
    db: AsyncSession, *, tenant_id: UUID, flat_id: UUID, payload: TenantVacate, actor: User
) -> tuple[Tenant, Flat]:
    tenant = await db.scalar(
        select(Tenant)
        .where(Tenant.id == tenant_id, Tenant.flat_id == flat_id)
        .with_for_update()
    )
    if tenant is None:
        raise AppError(404, "TENANT_NOT_FOUND", "Tenant not found.")
    if not tenant.is_active:
        raise AppError(409, "IMMUTABLE_RECORD", "This tenant has already been vacated.")

    flat = await db.scalar(select(Flat).where(Flat.id == flat_id).with_for_update())
    if flat is None:
        raise AppError(404, "FLAT_NOT_FOUND", "Flat not found.")

    before = {"occupancy_status": flat.occupancy_status}
    tenant.is_active = False
    tenant.vacated_at = datetime.now(UTC)
    tenant.vacated_by_user_id = actor.id
    if tenant.lease_end is None:
        tenant.lease_end = payload.vacated_date
    flat.occupancy_status = payload.occupancy_status
    await db.flush()

    await write_audit_log(
        db,
        actor=actor,
        tower_id=flat.tower_id,
        action="TENANT_VACATED",
        entity_type="Tenant",
        entity_id=tenant.id,
        before=before,
        after={"occupancy_status": flat.occupancy_status},
    )
    return tenant, flat
