"""Grace-period config — backend.md §6.2. Writes require `CONFIGURE_BILLING`; reads require
`VIEW_TOWER_DATA` (tower membership)."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_permission
from app.core.errors import AppError
from app.db.session import get_db
from app.models.association_member import AssociationMember
from app.models.grace_period_config import GracePeriodConfig
from app.models.user import User
from app.schemas.grace_period import GracePeriodConfigCreate, GracePeriodConfigOut
from app.services.audit import write_audit_log
from app.services.billing_formula import get_current_grace_period

router = APIRouter(prefix="/towers/{tower_id}/grace-period-config", tags=["maintenance-billing"])


def _grace_dict(config: GracePeriodConfig) -> dict:
    return {
        "grace_period_days": config.grace_period_days,
        "effective_from": config.effective_from.isoformat(),
    }


@router.post("", response_model=GracePeriodConfigOut, status_code=201)
async def create_grace_period_config(
    tower_id: UUID,
    payload: GracePeriodConfigCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    member: AssociationMember | None = Depends(require_permission("CONFIGURE_BILLING")),
) -> GracePeriodConfigOut:
    if member is None:
        raise AppError(
            422,
            "ASSOCIATION_MEMBERSHIP_REQUIRED",
            "This action requires an association-member identity.",
        )

    effective_from = payload.effective_from or date.today()
    previous = await get_current_grace_period(db, tower_id, date.today())

    existing = await db.scalar(
        select(GracePeriodConfig).where(
            GracePeriodConfig.tower_id == tower_id,
            GracePeriodConfig.effective_from == effective_from,
        )
    )
    if existing is not None:
        raise AppError(
            409,
            "GRACE_PERIOD_ALREADY_EXISTS_FOR_DATE",
            "A grace-period version already exists for this effective date.",
        )

    config = GracePeriodConfig(
        tower_id=tower_id,
        grace_period_days=payload.grace_period_days,
        effective_from=effective_from,
        created_by=member.id,
    )
    db.add(config)
    await db.flush()

    await write_audit_log(
        db,
        actor=current_user,
        tower_id=tower_id,
        action="grace_period_changed",
        entity_type="GracePeriodConfig",
        entity_id=config.id,
        before=_grace_dict(previous) if previous is not None else None,
        after=_grace_dict(config),
    )
    await db.commit()
    await db.refresh(config)
    return GracePeriodConfigOut.model_validate(config)


@router.get("/current", response_model=GracePeriodConfigOut)
async def get_current_grace_period_config(
    tower_id: UUID,
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("VIEW_TOWER_DATA")),
) -> GracePeriodConfigOut:
    config = await get_current_grace_period(db, tower_id, date.today())
    if config is None:
        raise AppError(
            404,
            "NO_GRACE_PERIOD_CONFIGURED",
            "This tower has not configured a grace period.",
        )
    return GracePeriodConfigOut.model_validate(config)
