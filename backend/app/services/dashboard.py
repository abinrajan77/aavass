"""Tower admin dashboard aggregation — `00-architecture-and-standards.md` §3.2's stat-card
set, read live off Modules 2-4's own tables every request (never a cached running total, per
`05-reporting-owner-portal-notifications/backend.md`'s "must never introduce a parallel/cached
snapshot" rule, which applies equally to this dashboard)."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expenditure import Expenditure
from app.models.flat import Flat
from app.models.maintenance_due import MaintenanceDue
from app.models.payment import Payment
from app.models.special_collection import SpecialCollection
from app.models.special_collection_due import SpecialCollectionDue
from app.schemas.dashboard import TowerDashboardStats


def _first_of_month(d: date) -> date:
    return d.replace(day=1)


def _first_of_next_month(d: date) -> date:
    return date(d.year + 1, 1, 1) if d.month == 12 else date(d.year, d.month + 1, 1)


async def get_tower_dashboard_stats(db: AsyncSession, *, tower_id: UUID) -> TowerDashboardStats:
    today = date.today()
    month_start = _first_of_month(today)
    month_end = _first_of_next_month(today)  # exclusive upper bound

    total_flats = await db.scalar(
        select(func.count()).select_from(Flat).where(
            Flat.tower_id == tower_id, Flat.deactivated_at.is_(None)
        )
    ) or 0
    occupied_flats = await db.scalar(
        select(func.count()).select_from(Flat).where(
            Flat.tower_id == tower_id,
            Flat.deactivated_at.is_(None),
            Flat.occupancy_status != "vacant",
        )
    ) or 0

    # Collections this month — payments.payment_date (when money was actually received), per
    # 05-reporting-owner-portal-notifications/backend.md §2.4's note that this (not the due's
    # own due_date) is the correct period-membership field; `due_type` alone discriminates
    # maintenance vs special_collection, no join/UNION needed (payments.tower_id is
    # denormalized), and UNIQUE(due_type, due_id) guarantees no double count.
    total_collected_this_month = await db.scalar(
        select(func.coalesce(func.sum(Payment.amount_received), 0)).where(
            Payment.tower_id == tower_id,
            Payment.payment_date >= month_start,
            Payment.payment_date < month_end,
        )
    ) or Decimal("0")

    pending_maintenance = await db.scalar(
        select(func.count()).select_from(MaintenanceDue).where(
            MaintenanceDue.tower_id == tower_id, MaintenanceDue.status == "pending"
        )
    ) or 0
    pending_special = await db.scalar(
        select(func.count()).select_from(SpecialCollectionDue).where(
            SpecialCollectionDue.tower_id == tower_id, SpecialCollectionDue.status == "pending"
        )
    ) or 0

    overdue_maintenance_count = await db.scalar(
        select(func.count()).select_from(MaintenanceDue).where(
            MaintenanceDue.tower_id == tower_id, MaintenanceDue.status == "overdue"
        )
    ) or 0
    overdue_special_count = await db.scalar(
        select(func.count()).select_from(SpecialCollectionDue).where(
            SpecialCollectionDue.tower_id == tower_id, SpecialCollectionDue.status == "overdue"
        )
    ) or 0
    overdue_maintenance_amount = await db.scalar(
        select(func.coalesce(func.sum(MaintenanceDue.amount), 0)).where(
            MaintenanceDue.tower_id == tower_id, MaintenanceDue.status == "overdue"
        )
    ) or Decimal("0")
    overdue_special_amount = await db.scalar(
        select(func.coalesce(func.sum(SpecialCollectionDue.amount), 0)).where(
            SpecialCollectionDue.tower_id == tower_id, SpecialCollectionDue.status == "overdue"
        )
    ) or Decimal("0")

    open_special_collections_count = await db.scalar(
        select(func.count(func.distinct(SpecialCollectionDue.special_collection_id)))
        .select_from(SpecialCollectionDue)
        .join(SpecialCollection, SpecialCollection.id == SpecialCollectionDue.special_collection_id)
        .where(
            SpecialCollection.tower_id == tower_id,
            SpecialCollection.deactivated_at.is_(None),
            SpecialCollectionDue.status != "paid",
        )
    ) or 0

    expenditure_this_month = await db.scalar(
        select(func.coalesce(func.sum(Expenditure.amount), 0)).where(
            Expenditure.tower_id == tower_id,
            Expenditure.deactivated_at.is_(None),
            Expenditure.expenditure_date >= month_start,
            Expenditure.expenditure_date < month_end,
        )
    ) or Decimal("0")

    return TowerDashboardStats(
        total_flats=total_flats,
        occupied_flats=occupied_flats,
        vacant_flats=total_flats - occupied_flats,
        total_collected_this_month=Decimal(total_collected_this_month),
        pending_dues_count=pending_maintenance + pending_special,
        overdue_dues_count=overdue_maintenance_count + overdue_special_count,
        overdue_amount=Decimal(overdue_maintenance_amount) + Decimal(overdue_special_amount),
        open_special_collections_count=open_special_collections_count,
        expenditure_this_month=Decimal(expenditure_this_month),
    )
