"""Tower business logic: code derivation, Admin-role seeding, and the (stubbed)
active-financials check used by tower deactivation."""

import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import ADMIN_ROLE_NAME, PERMISSION_CATALOG
from app.models.permission import Permission
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.tower import Tower


async def derive_unique_tower_code(
    db: AsyncSession, *, name: str, requested_code: str | None
) -> str:
    base = requested_code or re.sub(r"[^A-Z0-9]", "", name.upper())
    base = base[:10] or "TWR"
    candidate = base
    suffix = 1
    while await db.scalar(select(Tower).where(Tower.code == candidate)) is not None:
        suffix += 1
        candidate = f"{base[: 10 - len(str(suffix))]}{suffix}"
    return candidate


async def seed_admin_role(db: AsyncSession, *, tower_id: UUID) -> Role:
    """Seeds the tower's system-default `Admin` role with every permission in the catalog.
    Called in the same transaction as the `Tower` insert (caller commits once)."""
    admin_role = Role(tower_id=tower_id, name=ADMIN_ROLE_NAME, is_system_default=True)
    db.add(admin_role)
    await db.flush()

    permission_rows = (await db.execute(select(Permission))).scalars().all()
    catalog_codes = {code for code, _ in PERMISSION_CATALOG}
    for perm in permission_rows:
        if perm.code in catalog_codes:
            db.add(RolePermission(role_id=admin_role.id, permission_id=perm.id))
    await db.flush()
    return admin_role


async def tower_has_active_financials(db: AsyncSession, *, tower_id: UUID) -> bool:
    """Whether the tower has any Pending/Overdue maintenance or special-collection due.

    TODO(module-3/4): Modules 3 (Maintenance Billing) and 4 (Special Collections &
    Expenditure) own the `maintenance_dues` / `special_collection_dues` tables that this
    check needs to query (per overview.md's edge case: "Deactivating a tower with active
    flats/dues is blocked with 409 TOWER_HAS_ACTIVE_FINANCIALS if any Pending/Overdue ...
    due exists"). Those tables don't exist yet in this codebase, so this stub always
    reports "no active financials found" (i.e. deactivation is never blocked by this
    specific check). Replace this function body with a real query against
    `maintenance_dues`/`special_collection_dues` (status IN ('Pending', 'Overdue') AND
    tower_id = :tower_id) once Module 3/4 land — do not fake the whole feature by
    hardcoding a block, only the missing data dependency is stubbed.
    """
    return False
