"""Maintenance-formula config — backend.md §6.1. Writes require `CONFIGURE_BILLING`; reads
require `VIEW_TOWER_DATA` (tower membership)."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_permission
from app.core.errors import AppError
from app.core.pagination import Pagination, pagination_params
from app.db.session import get_db
from app.models.association_member import AssociationMember
from app.models.maintenance_formula import MaintenanceFormula
from app.models.user import User
from app.schemas.common import PageEnvelope
from app.schemas.maintenance_formula import MaintenanceFormulaCreate, MaintenanceFormulaOut
from app.services.audit import write_audit_log
from app.services.billing_formula import get_current_formula

router = APIRouter(prefix="/towers/{tower_id}/maintenance-formula", tags=["maintenance-billing"])

_CENTS = Decimal("0.01")


def _formula_dict(formula: MaintenanceFormula) -> dict:
    # Quantize explicitly rather than relying on the column's post-flush precision: before a
    # `db.refresh()`, `formula.base_amount`/`per_sqft_rate` still hold whatever Decimal Pydantic
    # parsed from the request body (which can render as e.g. "2500.0" depending on the JSON
    # literal), not the DB's NUMERIC(12,2)-normalized value — quantizing keeps the audit
    # snapshot's precision consistent regardless of when it's taken relative to a refresh.
    return {
        "base_amount": str(formula.base_amount.quantize(_CENTS)),
        "per_sqft_rate": str(formula.per_sqft_rate.quantize(_CENTS)),
        "effective_from": formula.effective_from.isoformat(),
    }


@router.post("", response_model=MaintenanceFormulaOut, status_code=201)
async def create_maintenance_formula(
    tower_id: UUID,
    payload: MaintenanceFormulaCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    member: AssociationMember | None = Depends(require_permission("CONFIGURE_BILLING")),
) -> MaintenanceFormulaOut:
    if member is None:
        raise AppError(
            422,
            "ASSOCIATION_MEMBERSHIP_REQUIRED",
            "This action requires an association-member identity.",
        )

    effective_from = payload.effective_from or date.today()
    previous = await get_current_formula(db, tower_id, date.today())

    existing = await db.scalar(
        select(MaintenanceFormula).where(
            MaintenanceFormula.tower_id == tower_id,
            MaintenanceFormula.effective_from == effective_from,
        )
    )
    if existing is not None:
        raise AppError(
            409,
            "FORMULA_ALREADY_EXISTS_FOR_DATE",
            "A maintenance formula version already exists for this effective date.",
        )

    formula = MaintenanceFormula(
        tower_id=tower_id,
        base_amount=payload.base_amount,
        per_sqft_rate=payload.per_sqft_rate,
        effective_from=effective_from,
        created_by=member.id,
    )
    db.add(formula)
    await db.flush()

    await write_audit_log(
        db,
        actor=current_user,
        tower_id=tower_id,
        action="formula_changed",
        entity_type="MaintenanceFormula",
        entity_id=formula.id,
        before=_formula_dict(previous) if previous is not None else None,
        after=_formula_dict(formula),
    )
    await db.commit()
    await db.refresh(formula)
    return MaintenanceFormulaOut.model_validate(formula)


@router.get("", response_model=PageEnvelope[MaintenanceFormulaOut])
async def list_maintenance_formulas(
    tower_id: UUID,
    pagination: Pagination = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("VIEW_TOWER_DATA")),
) -> PageEnvelope[MaintenanceFormulaOut]:
    total = await db.scalar(
        select(func.count())
        .select_from(MaintenanceFormula)
        .where(MaintenanceFormula.tower_id == tower_id)
    )
    rows = (
        (
            await db.execute(
                select(MaintenanceFormula)
                .where(MaintenanceFormula.tower_id == tower_id)
                .order_by(MaintenanceFormula.effective_from.desc())
                .offset(pagination.offset)
                .limit(pagination.page_size)
            )
        )
        .scalars()
        .all()
    )
    return PageEnvelope(
        items=[MaintenanceFormulaOut.model_validate(r) for r in rows],
        page=pagination.page,
        page_size=pagination.page_size,
        total=total or 0,
    )


@router.get("/current", response_model=MaintenanceFormulaOut)
async def get_current_maintenance_formula(
    tower_id: UUID,
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("VIEW_TOWER_DATA")),
) -> MaintenanceFormulaOut:
    formula = await get_current_formula(db, tower_id, date.today())
    if formula is None:
        raise AppError(
            404, "NO_FORMULA_CONFIGURED", "This tower has not configured a maintenance formula."
        )
    return MaintenanceFormulaOut.model_validate(formula)
