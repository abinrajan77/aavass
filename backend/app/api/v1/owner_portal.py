"""Owner self-service portal — backend.md §3. Guarded by `app.api.deps_owner` (an authenticated
flat-owner user resolved via `Owner.user_id`), never `require_permission()` — flat owners are
not `association_members` (`00-architecture-and-standards.md` §5.2).

Not the same as Module 2's `GET /api/v1/me/flats` (`app/api/v1/me_flats.py`) — see
`flats-summary` below and backend.md §3.1's note. Do not merge these or repoint either one."""

from datetime import date
from decimal import Decimal
from typing import Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps_owner import OwnedFlatAccess, require_owned_flat, require_owner
from app.db.session import get_db
from app.models.flat import Flat
from app.models.flat_ownership import FlatOwnership
from app.models.maintenance_due import MaintenanceDue
from app.models.owner import Owner
from app.models.payment import Payment
from app.models.receipt import Receipt
from app.models.tower import Tower
from app.schemas.owner_portal import (
    OwnedFlatsByTower,
    OwnedFlatsResponse,
    OwnedFlatSummary,
    OwnerFlatDashboardResponse,
    ReceiptSummary,
)
from app.services import reporting, storage

router = APIRouter(prefix="/owners/me", tags=["owner-portal"])


async def _current_due_status(
    db: AsyncSession, *, flat_id: UUID
) -> Literal["paid", "pending", "overdue", "no_active_due"]:
    """The status of the most recently generated `maintenance_dues` row for this flat — "current
    due" per backend.md §3.1's `OwnedFlatSummary.current_due_status`. `no_active_due` if no
    billing cycle has ever generated a due for this flat yet."""
    latest_status = await db.scalar(
        select(MaintenanceDue.status)
        .where(MaintenanceDue.flat_id == flat_id)
        .order_by(MaintenanceDue.due_date.desc(), MaintenanceDue.created_at.desc())
        .limit(1)
    )
    if latest_status is None:
        return "no_active_due"
    return cast(Literal["paid", "pending", "overdue"], latest_status)


@router.get("/flats-summary", response_model=OwnedFlatsResponse)
async def get_flats_summary(
    owner: Owner = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
) -> OwnedFlatsResponse:
    rows = (
        await db.execute(
            select(FlatOwnership, Flat, Tower)
            .join(Flat, Flat.id == FlatOwnership.flat_id)
            .join(Tower, Tower.id == Flat.tower_id)
            .where(FlatOwnership.owner_id == owner.id, FlatOwnership.date_to.is_(None))
            .order_by(Tower.name.asc(), Flat.flat_number.asc())
        )
    ).all()

    towers: dict[UUID, OwnedFlatsByTower] = {}
    for ownership, flat, tower in rows:
        due_status = await _current_due_status(db, flat_id=flat.id)
        summary = OwnedFlatSummary(
            flat_id=flat.id,
            tower_id=tower.id,
            tower_name=tower.name,
            flat_number=flat.flat_number,
            occupancy_status=cast(
                Literal["owner_occupied", "tenant_occupied", "vacant"], flat.occupancy_status
            ),
            is_primary_owner=ownership.is_primary_contact,
            current_due_status=due_status,
        )
        if tower.id not in towers:
            towers[tower.id] = OwnedFlatsByTower(
                tower_id=tower.id, tower_name=tower.name, flats=[]
            )
        towers[tower.id].flats.append(summary)

    return OwnedFlatsResponse(towers=list(towers.values()))


async def _ytd_totals(
    db: AsyncSession, *, flat_id: UUID, fy_start: date, fy_end: date
) -> dict[str, Decimal]:
    total_due_ytd = (
        await db.scalar(
            select(func.coalesce(func.sum(MaintenanceDue.amount), 0)).where(
                MaintenanceDue.flat_id == flat_id,
                MaintenanceDue.due_date >= fy_start,
                MaintenanceDue.due_date <= fy_end,
            )
        )
        or Decimal("0.00")
    )
    total_paid_ytd = (
        await db.scalar(
            select(func.coalesce(func.sum(Payment.amount_received), 0))
            .select_from(Payment)
            .join(MaintenanceDue, MaintenanceDue.id == Payment.due_id)
            .where(
                Payment.due_type == "maintenance",
                MaintenanceDue.flat_id == flat_id,
                Payment.payment_date >= fy_start,
                Payment.payment_date <= fy_end,
            )
        )
        or Decimal("0.00")
    )
    return {
        "total_due_ytd": Decimal(total_due_ytd),
        "total_paid_ytd": Decimal(total_paid_ytd),
    }


@router.get("/flats/{flat_id}/dashboard", response_model=OwnerFlatDashboardResponse)
async def get_flat_dashboard(
    access: OwnedFlatAccess = Depends(require_owned_flat),
    db: AsyncSession = Depends(get_db),
) -> OwnerFlatDashboardResponse:
    flat = access.flat
    tower_id = flat.tower_id

    payment_history = await reporting.build_collection_rows_for_flat(db, flat_id=flat.id)
    current_due = payment_history[0] if payment_history else None

    # Receipts for this flat's maintenance dues — `receipts.due_id` is polymorphic (no DB FK),
    # so correlate through `maintenance_dues.flat_id` rather than joining `receipts` to `Flat`
    # directly (this dashboard is maintenance-scoped per backend.md §3.2's schema; special-
    # collection receipts aren't part of this response shape).
    receipt_rows = (
        await db.execute(
            select(Receipt)
            .join(MaintenanceDue, MaintenanceDue.id == Receipt.due_id)
            .where(Receipt.due_type == "maintenance", MaintenanceDue.flat_id == flat.id)
            .order_by(Receipt.generated_at.desc())
        )
    ).scalars().all()
    receipts = [
        ReceiptSummary(
            receipt_id=receipt.id,
            receipt_number=receipt.receipt_number,
            billing_period=receipt.billing_period_label,
            download_url=await storage.presigned_get_url(key=receipt.pdf_s3_key),
        )
        for receipt in receipt_rows
    ]

    fy_start, fy_end = reporting.financial_year_for(date.today())
    expenditure_report = await reporting.build_expenditure_report(
        db, tower_id=tower_id, period_start=fy_start, period_end=fy_end
    )

    tenant_history = (
        await reporting.build_tenant_register_report(db, tower_id=tower_id, flat_id=flat.id)
    ).items

    ytd_totals = await _ytd_totals(db, flat_id=flat.id, fy_start=fy_start, fy_end=fy_end)

    return OwnerFlatDashboardResponse(
        flat_id=flat.id,
        tower_id=tower_id,
        flat_number=flat.flat_number,
        current_due=current_due,
        payment_history=payment_history,
        receipts=receipts,
        tower_expenditures=expenditure_report.items,
        tenant_history=tenant_history,
        ytd_totals=ytd_totals,
    )
