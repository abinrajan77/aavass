"""Billing cycles — backend.md §6.3. Writes require `CREATE_BILLING_CYCLE`; reads require
`VIEW_TOWER_DATA` (tower membership). `POST` branches sync/async per
`00-architecture-and-standards.md` §4's bulk-write latency budget (<=300 active flats
synchronous, beyond that an SQS-backed async job — see `app.services.billing_cycle` /
`app.services.sqs` / `app.services.jobs`)."""

from decimal import Decimal
from typing import Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_permission
from app.core.errors import AppError
from app.core.pagination import Pagination, pagination_params
from app.db.session import get_db
from app.models.association_member import AssociationMember
from app.models.billing_cycle import BillingCycle
from app.models.maintenance_due import MaintenanceDue
from app.models.user import User
from app.schemas.billing_cycle import BillingCycleCreate, BillingCycleOut, BillingCycleUpdate
from app.schemas.common import PageEnvelope
from app.services import flats_service, sqs
from app.services import jobs as jobs_service
from app.services.billing_cycle import (
    SYNC_GENERATION_FLAT_THRESHOLD,
    create_cycle_row,
    generate_dues_sync,
)

router = APIRouter(prefix="/towers/{tower_id}/billing-cycles", tags=["maintenance-billing"])


async def _aggregates_for_cycles(db: AsyncSession, cycle_ids: list[UUID]) -> dict[UUID, dict]:
    if not cycle_ids:
        return {}
    rows = (
        await db.execute(
            select(
                MaintenanceDue.billing_cycle_id,
                func.count().label("total_dues"),
                func.coalesce(
                    func.sum(
                        case((MaintenanceDue.status == "paid", MaintenanceDue.amount), else_=0)
                    ),
                    0,
                ).label("total_collected"),
                func.coalesce(
                    func.sum(case((MaintenanceDue.status == "pending", 1), else_=0)), 0
                ).label("pending_count"),
                func.coalesce(
                    func.sum(case((MaintenanceDue.status == "overdue", 1), else_=0)), 0
                ).label("overdue_count"),
            )
            .where(MaintenanceDue.billing_cycle_id.in_(cycle_ids))
            .group_by(MaintenanceDue.billing_cycle_id)
        )
    ).all()
    return {
        row.billing_cycle_id: {
            "total_dues": row.total_dues,
            "total_collected": Decimal(row.total_collected),
            "pending_count": row.pending_count,
            "overdue_count": row.overdue_count,
        }
        for row in rows
    }


def _to_cycle_out(
    cycle: BillingCycle, agg: dict | None, *, generation_failures: list[dict] | None = None
) -> BillingCycleOut:
    agg = agg or {
        "total_dues": 0,
        "total_collected": Decimal("0.00"),
        "pending_count": 0,
        "overdue_count": 0,
    }
    return BillingCycleOut(
        id=cycle.id,
        tower_id=cycle.tower_id,
        month=cycle.month,
        year=cycle.year,
        due_date=cycle.due_date,
        # `cycle.status` is a plain `str` column (see app/models/billing_cycle.py); its values
        # are constrained to this Literal only by application-level invariants, not a DB enum.
        status=cast(Literal["generating", "active"], cycle.status),
        formula_id=cycle.formula_id,
        grace_period_days_snapshot=cycle.grace_period_days_snapshot,
        created_at=cycle.created_at,
        total_dues=agg["total_dues"],
        total_collected=agg["total_collected"],
        pending_count=agg["pending_count"],
        overdue_count=agg["overdue_count"],
        generation_failures=generation_failures,
    )


@router.post("", status_code=201)
async def create_billing_cycle(
    tower_id: UUID,
    payload: BillingCycleCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    member: AssociationMember | None = Depends(require_permission("CREATE_BILLING_CYCLE")),
):
    if member is None:
        raise AppError(
            422,
            "ASSOCIATION_MEMBERSHIP_REQUIRED",
            "This action requires an association-member identity.",
        )

    cycle = await create_cycle_row(
        db,
        tower_id=tower_id,
        month=payload.month,
        year=payload.year,
        due_date=payload.due_date,
        created_by_id=member.id,
    )

    active_flat_count = await flats_service.count_active(db, tower_id)

    if active_flat_count <= SYNC_GENERATION_FLAT_THRESHOLD:
        failures = await generate_dues_sync(db, cycle=cycle)
        await db.commit()
        await db.refresh(cycle)
        agg = await _aggregates_for_cycles(db, [cycle.id])
        out = _to_cycle_out(
            cycle,
            agg.get(cycle.id),
            generation_failures=[f.__dict__ for f in failures] if failures else None,
        )
        return JSONResponse(status_code=201, content=out.model_dump(mode="json"))

    idempotency_key = f"{tower_id}:{payload.month}:{payload.year}"
    job = await jobs_service.create_job(
        db,
        tower_id=tower_id,
        job_type="billing_cycle",
        payload={
            "tower_id": str(tower_id),
            "cycle_id": str(cycle.id),
            "month": payload.month,
            "year": payload.year,
        },
        idempotency_key=idempotency_key,
    )
    cycle.job_id = job.id
    await db.commit()

    await sqs.enqueue(
        queue_name="billing-cycle-jobs",
        payload={
            "tower_id": str(tower_id),
            "cycle_id": str(cycle.id),
            "month": payload.month,
            "year": payload.year,
        },
        idempotency_key=idempotency_key,
    )

    return JSONResponse(
        status_code=202,
        content={"cycle_id": str(cycle.id), "job_id": str(job.id), "status": "generating"},
    )


@router.get("", response_model=PageEnvelope[BillingCycleOut])
async def list_billing_cycles(
    tower_id: UUID,
    pagination: Pagination = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("VIEW_TOWER_DATA")),
) -> PageEnvelope[BillingCycleOut]:
    total = await db.scalar(
        select(func.count()).select_from(BillingCycle).where(BillingCycle.tower_id == tower_id)
    )
    rows = (
        (
            await db.execute(
                select(BillingCycle)
                .where(BillingCycle.tower_id == tower_id)
                .order_by(BillingCycle.year.desc(), BillingCycle.month.desc())
                .offset(pagination.offset)
                .limit(pagination.page_size)
            )
        )
        .scalars()
        .all()
    )
    agg = await _aggregates_for_cycles(db, [r.id for r in rows])
    return PageEnvelope(
        items=[_to_cycle_out(r, agg.get(r.id)) for r in rows],
        page=pagination.page,
        page_size=pagination.page_size,
        total=total or 0,
    )


async def _get_cycle_or_404(db: AsyncSession, tower_id: UUID, cycle_id: UUID) -> BillingCycle:
    cycle = await db.scalar(
        select(BillingCycle).where(BillingCycle.id == cycle_id, BillingCycle.tower_id == tower_id)
    )
    if cycle is None:
        raise AppError(404, "BILLING_CYCLE_NOT_FOUND", "Billing cycle not found.")
    return cycle


@router.get("/{cycle_id}", response_model=BillingCycleOut)
async def get_billing_cycle(
    tower_id: UUID,
    cycle_id: UUID,
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("VIEW_TOWER_DATA")),
) -> BillingCycleOut:
    cycle = await _get_cycle_or_404(db, tower_id, cycle_id)
    agg = await _aggregates_for_cycles(db, [cycle.id])
    return _to_cycle_out(cycle, agg.get(cycle.id))


@router.put("/{cycle_id}", response_model=BillingCycleOut)
async def update_billing_cycle(
    tower_id: UUID,
    cycle_id: UUID,
    payload: BillingCycleUpdate,
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("CREATE_BILLING_CYCLE")),
) -> BillingCycleOut:
    cycle = await _get_cycle_or_404(db, tower_id, cycle_id)

    dues_count = await db.scalar(
        select(func.count())
        .select_from(MaintenanceDue)
        .where(MaintenanceDue.billing_cycle_id == cycle.id)
    )
    if cycle.status != "generating" or (dues_count or 0) > 0:
        raise AppError(
            409,
            "IMMUTABLE_RECORD",
            "This billing cycle is immutable once dues exist.",
        )

    cycle.due_date = payload.due_date
    await db.commit()
    await db.refresh(cycle)
    agg = await _aggregates_for_cycles(db, [cycle.id])
    return _to_cycle_out(cycle, agg.get(cycle.id))


@router.delete("/{cycle_id}")
async def delete_billing_cycle(
    tower_id: UUID,
    cycle_id: UUID,
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("CREATE_BILLING_CYCLE")),
):
    # Always immutable — no hard delete of financial records, ever (PRD §7; backend.md §6.3).
    await _get_cycle_or_404(db, tower_id, cycle_id)
    raise AppError(
        409, "IMMUTABLE_RECORD", "Billing cycles can never be deleted."
    )


# Re-exported for the sibling `maintenance_dues` router, which needs the same 404 helper for
# cycle-scoped dues routes without duplicating the lookup.
__all__ = ["router", "_get_cycle_or_404"]
