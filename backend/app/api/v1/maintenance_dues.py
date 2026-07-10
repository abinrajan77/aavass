"""Maintenance dues — backend.md §6.4. Reads need tower membership (`VIEW_TOWER_DATA`);
`mark-paid` needs `RECORD_PAYMENT`. All routes are tower-scoped per
`00-architecture-and-standards.md` §6 (no top-level `/api/v1/dues/...`)."""

from decimal import Decimal
from typing import Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_permission
from app.api.v1.billing_cycles import _get_cycle_or_404
from app.core.errors import AppError
from app.core.pagination import Pagination, pagination_params
from app.db.session import get_db
from app.models.association_member import AssociationMember
from app.models.flat import Flat
from app.models.maintenance_due import MaintenanceDue
from app.models.receipt import Receipt
from app.models.user import User
from app.schemas.common import PageEnvelope
from app.schemas.maintenance_due import BillingDashboardStatsOut, MaintenanceDueOut
from app.schemas.payment import MarkPaidRequest
from app.schemas.receipt import MarkPaidResponse, ReceiptDownloadOut, ReceiptOut
from app.services import storage
from app.services.payments import record_payment

router = APIRouter(prefix="/towers/{tower_id}", tags=["maintenance-billing"])


def _to_due_out(due: MaintenanceDue, flat_number: str) -> MaintenanceDueOut:
    # `due.assigned_to_type`/`due.status` are plain `str` columns (see
    # app/models/maintenance_due.py); values are constrained to these Literals only by
    # application-level invariants, not a DB enum.
    return MaintenanceDueOut(
        id=due.id,
        billing_cycle_id=due.billing_cycle_id,
        flat_id=due.flat_id,
        flat_number=flat_number,
        amount=due.amount,
        assigned_to_type=cast(Literal["tenant", "owner"], due.assigned_to_type),
        assigned_to_name_snapshot=due.assigned_to_name_snapshot,
        due_date=due.due_date,
        status=cast(Literal["pending", "paid", "overdue"], due.status),
        created_at=due.created_at,
    )


async def _paginated_dues(
    db: AsyncSession,
    *,
    conditions: list,
    pagination: Pagination,
) -> PageEnvelope[MaintenanceDueOut]:
    total = await db.scalar(
        select(func.count()).select_from(MaintenanceDue).where(*conditions)
    )
    rows = (
        await db.execute(
            select(MaintenanceDue, Flat.flat_number)
            .join(Flat, Flat.id == MaintenanceDue.flat_id)
            .where(*conditions)
            .order_by(MaintenanceDue.due_date.desc())
            .offset(pagination.offset)
            .limit(pagination.page_size)
        )
    ).all()
    return PageEnvelope(
        items=[_to_due_out(due, flat_number) for due, flat_number in rows],
        page=pagination.page,
        page_size=pagination.page_size,
        total=total or 0,
    )


@router.get("/billing-cycles/{cycle_id}/dues", response_model=PageEnvelope[MaintenanceDueOut])
async def list_dues_for_cycle(
    tower_id: UUID,
    cycle_id: UUID,
    status_filter: Literal["pending", "paid", "overdue"] | None = Query(
        default=None, alias="status"
    ),
    pagination: Pagination = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("VIEW_TOWER_DATA")),
) -> PageEnvelope[MaintenanceDueOut]:
    await _get_cycle_or_404(db, tower_id, cycle_id)
    conditions = [MaintenanceDue.billing_cycle_id == cycle_id, MaintenanceDue.tower_id == tower_id]
    if status_filter is not None:
        conditions.append(MaintenanceDue.status == status_filter)
    return await _paginated_dues(db, conditions=conditions, pagination=pagination)


@router.get("/dues", response_model=PageEnvelope[MaintenanceDueOut])
async def list_dues_cross_cycle(
    tower_id: UUID,
    status_filter: Literal["pending", "overdue"] | None = Query(default=None, alias="status"),
    pagination: Pagination = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("VIEW_TOWER_DATA")),
) -> PageEnvelope[MaintenanceDueOut]:
    """Cross-cycle "at a glance" dashboard view (PRD §6.3.4)."""
    conditions = [MaintenanceDue.tower_id == tower_id]
    if status_filter is not None:
        conditions.append(MaintenanceDue.status == status_filter)
    return await _paginated_dues(db, conditions=conditions, pagination=pagination)


@router.get("/billing-dashboard-stats", response_model=BillingDashboardStatsOut)
async def get_billing_dashboard_stats(
    tower_id: UUID,
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("VIEW_TOWER_DATA")),
) -> BillingDashboardStatsOut:
    """Feeds the `NumberTicker` stat cards. "This cycle" = the tower's most recently created
    active billing cycle; pending/overdue figures are tower-wide (cross-cycle), matching the
    cross-cycle `dues` list endpoint above."""
    from app.models.billing_cycle import BillingCycle

    current_cycle_id = await db.scalar(
        select(BillingCycle.id)
        .where(BillingCycle.tower_id == tower_id, BillingCycle.status == "active")
        .order_by(BillingCycle.year.desc(), BillingCycle.month.desc())
        .limit(1)
    )

    total_collected_this_cycle = Decimal("0.00")
    if current_cycle_id is not None:
        total_collected_this_cycle = await db.scalar(
            select(func.coalesce(func.sum(MaintenanceDue.amount), 0)).where(
                MaintenanceDue.billing_cycle_id == current_cycle_id,
                MaintenanceDue.status == "paid",
            )
        ) or Decimal("0.00")

    pending_count = (
        await db.scalar(
            select(func.count())
            .select_from(MaintenanceDue)
            .where(MaintenanceDue.tower_id == tower_id, MaintenanceDue.status == "pending")
        )
        or 0
    )
    overdue_amount = await db.scalar(
        select(func.coalesce(func.sum(MaintenanceDue.amount), 0)).where(
            MaintenanceDue.tower_id == tower_id, MaintenanceDue.status == "overdue"
        )
    ) or Decimal("0.00")

    return BillingDashboardStatsOut(
        total_collected_this_cycle=Decimal(total_collected_this_cycle),
        pending_count=pending_count,
        overdue_amount=Decimal(overdue_amount),
    )


async def _get_due_or_404(db: AsyncSession, tower_id: UUID, due_id: UUID) -> MaintenanceDue:
    due = await db.scalar(
        select(MaintenanceDue).where(
            MaintenanceDue.id == due_id, MaintenanceDue.tower_id == tower_id
        )
    )
    if due is None:
        raise AppError(404, "DUE_NOT_FOUND", "Maintenance due not found.")
    return due


@router.get("/dues/{due_id}", response_model=MaintenanceDueOut)
async def get_due(
    tower_id: UUID,
    due_id: UUID,
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("VIEW_TOWER_DATA")),
) -> MaintenanceDueOut:
    due = await _get_due_or_404(db, tower_id, due_id)
    flat = await db.get(Flat, due.flat_id)
    return _to_due_out(due, flat.flat_number if flat is not None else "")


@router.patch("/dues/{due_id}/mark-paid", response_model=MarkPaidResponse)
async def mark_due_paid(
    tower_id: UUID,
    due_id: UUID,
    payload: MarkPaidRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    member: AssociationMember | None = Depends(require_permission("RECORD_PAYMENT")),
) -> MarkPaidResponse:
    if member is None:
        raise AppError(
            422,
            "ASSOCIATION_MEMBERSHIP_REQUIRED",
            "This action requires an association-member identity.",
        )

    receipt = await record_payment(
        db,
        tower_id=tower_id,
        due_type="maintenance",
        due_id=due_id,
        payment_date=payload.payment_date,
        amount_received=payload.amount_received,
        payment_mode=payload.payment_mode,
        reference_number=payload.reference_number,
        recorded_by=member,
    )

    due = await _get_due_or_404(db, tower_id, due_id)
    flat = await db.get(Flat, due.flat_id)
    download_url = await storage.presigned_get_url(key=receipt.pdf_s3_key)

    return MarkPaidResponse(
        due=_to_due_out(due, flat.flat_number if flat is not None else ""),
        receipt=ReceiptOut(
            id=receipt.id,
            receipt_number=receipt.receipt_number,
            owner_name_snapshot=receipt.owner_name_snapshot,
            billing_period_label=receipt.billing_period_label,
            generated_at=receipt.generated_at,
            download_url=download_url,
        ),
    )


@router.get("/dues/{due_id}/receipt", response_model=ReceiptDownloadOut)
async def get_due_receipt(
    tower_id: UUID,
    due_id: UUID,
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("VIEW_TOWER_DATA")),
) -> ReceiptDownloadOut:
    due = await _get_due_or_404(db, tower_id, due_id)
    if due.status != "paid":
        raise AppError(404, "RECEIPT_NOT_AVAILABLE", "This due has not been paid yet.")

    receipt = await db.scalar(
        select(Receipt).where(Receipt.due_type == "maintenance", Receipt.due_id == due_id)
    )
    if receipt is None:
        raise AppError(404, "RECEIPT_NOT_AVAILABLE", "No receipt exists for this due.")

    download_url = await storage.presigned_get_url(key=receipt.pdf_s3_key)
    return ReceiptDownloadOut(receipt_number=receipt.receipt_number, download_url=download_url)
