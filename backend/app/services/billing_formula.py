"""Formula calculation (backend.md §2) + versioned formula/grace-period lookups.

Both `MaintenanceFormula` and `GracePeriodConfig` are append-only, `effective_from`-versioned
tables (backend.md §1.1/§1.2). "Current" for a tower at date `d` is always the row with the
latest `effective_from <= d` — never the tower's absolute-latest row, since a future-dated
version may already exist (overview.md edge case 14).
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.grace_period_config import GracePeriodConfig
from app.models.maintenance_formula import MaintenanceFormula

_CENTS = Decimal("0.01")


def calculate_monthly_maintenance(
    base_amount: Decimal, per_sqft_rate: Decimal, carpet_area: Decimal
) -> Decimal:
    """`Monthly Maintenance = Base Amount + (Carpet Area x Per Sq Ft Rate)` (PRD §6.3.1).

    The area component is rounded half-up to the nearest paisa *before* adding the base
    amount (overview.md edge case 13), then the total is rounded again as a safety net (a
    no-op when both inputs already carry <=2 decimal places, but keeps the contract exact if a
    caller ever passes a base_amount with more precision).
    """
    area_component = (carpet_area * per_sqft_rate).quantize(_CENTS, rounding=ROUND_HALF_UP)
    return (base_amount + area_component).quantize(_CENTS, rounding=ROUND_HALF_UP)


async def get_current_formula(
    db: AsyncSession, tower_id: UUID, as_of: date
) -> MaintenanceFormula | None:
    return await db.scalar(
        select(MaintenanceFormula)
        .where(MaintenanceFormula.tower_id == tower_id, MaintenanceFormula.effective_from <= as_of)
        .order_by(MaintenanceFormula.effective_from.desc())
        .limit(1)
    )


async def get_current_grace_period(
    db: AsyncSession, tower_id: UUID, as_of: date
) -> GracePeriodConfig | None:
    return await db.scalar(
        select(GracePeriodConfig)
        .where(GracePeriodConfig.tower_id == tower_id, GracePeriodConfig.effective_from <= as_of)
        .order_by(GracePeriodConfig.effective_from.desc())
        .limit(1)
    )
