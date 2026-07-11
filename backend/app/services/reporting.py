"""Report aggregation queries — backend.md §2.1-2.5. Purely a read/aggregation layer over
Module 2/3/4's own tables (`00-architecture-and-standards.md` §7): every function here reads
`payments`/`expenditures`/etc. directly at call time, never a cached/pre-computed running total
that could drift from those modules' own numbers (backend.md "What must NOT break").

Each report exposes a cheap `count_*` function (COUNT-only query, no row materialization) used
by `app.services.export` to decide sync-vs-async *before* paying the cost of building the full
row list, and a `build_*` function that returns the actual Pydantic response used by both the
JSON-preview branch and the CSV/PDF export renderers.
"""

from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.billing_cycle import BillingCycle
from app.models.expenditure import Expenditure
from app.models.flat import Flat
from app.models.flat_ownership import FlatOwnership
from app.models.maintenance_due import MaintenanceDue
from app.models.owner import Owner
from app.models.payment import Payment
from app.models.receipt import Receipt
from app.models.special_collection_due import SpecialCollectionDue
from app.models.tenant import Tenant
from app.schemas.report import (
    CategoryTotal,
    CollectionReportResponse,
    CollectionReportRow,
    CollectionVsExpenditureResponse,
    ExpenditureReportResponse,
    ExpenditureReportRow,
    OutstandingDueRow,
    OutstandingDuesReportResponse,
    TenantRegisterResponse,
    TenantRegisterRow,
)

MONTH_NAMES = [
    "",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]


def month_bounds(month: int, year: int) -> tuple[date, date]:
    if month == 12:
        next_month_start = date(year + 1, 1, 1)
    else:
        next_month_start = date(year, month + 1, 1)
    return date(year, month, 1), next_month_start - timedelta(days=1)


def financial_year_bounds(fy_start_year: int) -> tuple[date, date]:
    """India-convention FY: Apr 1 (`fy_start_year`) - Mar 31 (`fy_start_year + 1`)."""
    return date(fy_start_year, 4, 1), date(fy_start_year + 1, 3, 31)


def financial_year_for(as_of: date) -> tuple[date, date]:
    """The financial year currently in effect for `as_of` (Apr 1 - Mar 31)."""
    fy_start_year = as_of.year if as_of.month >= 4 else as_of.year - 1
    return financial_year_bounds(fy_start_year)


async def _owner_names_by_flat(db: AsyncSession, flat_ids: list[UUID]) -> dict[UUID, list[str]]:
    """Every currently-active (`date_to IS NULL`) owner's name per flat, primary contact
    first — `CollectionReportRow.owner_names` is a list because a flat can be co-owned."""
    if not flat_ids:
        return {}
    rows = (
        await db.execute(
            select(FlatOwnership.flat_id, Owner.full_name, FlatOwnership.is_primary_contact)
            .join(Owner, Owner.id == FlatOwnership.owner_id)
            .where(FlatOwnership.flat_id.in_(flat_ids), FlatOwnership.date_to.is_(None))
            .order_by(FlatOwnership.is_primary_contact.desc(), Owner.full_name.asc())
        )
    ).all()
    result: dict[UUID, list[str]] = defaultdict(list)
    for flat_id, full_name, _is_primary in rows:
        result[flat_id].append(full_name)
    return dict(result)


# --------------------------------------------------------------------------------------------
# 2.1 Collection report
# --------------------------------------------------------------------------------------------


async def count_collection_rows(db: AsyncSession, *, tower_id: UUID, billing_cycle_id: UUID) -> int:
    return (
        await db.scalar(
            select(func.count())
            .select_from(MaintenanceDue)
            .where(
                MaintenanceDue.tower_id == tower_id,
                MaintenanceDue.billing_cycle_id == billing_cycle_id,
            )
        )
        or 0
    )


async def build_collection_report(
    db: AsyncSession, *, tower_id: UUID, billing_cycle_id: UUID
) -> CollectionReportResponse:
    cycle = await db.get(BillingCycle, billing_cycle_id)
    if cycle is None or cycle.tower_id != tower_id:
        raise AppError(404, "BILLING_CYCLE_NOT_FOUND", "Billing cycle not found.")

    rows = (
        await db.execute(
            select(MaintenanceDue, Flat.flat_number)
            .join(Flat, Flat.id == MaintenanceDue.flat_id)
            .where(MaintenanceDue.billing_cycle_id == billing_cycle_id)
            .order_by(Flat.flat_number.asc())
        )
    ).all()

    due_ids = [due.id for due, _ in rows]
    flat_ids = [due.flat_id for due, _ in rows]
    owner_names = await _owner_names_by_flat(db, flat_ids)

    payments_by_due: dict[UUID, Payment] = {}
    receipts_by_due: dict[UUID, Receipt] = {}
    if due_ids:
        payment_rows = (
            await db.execute(
                select(Payment).where(
                    Payment.due_type == "maintenance", Payment.due_id.in_(due_ids)
                )
            )
        ).scalars().all()
        payments_by_due = {p.due_id: p for p in payment_rows}

        receipt_rows = (
            await db.execute(
                select(Receipt).where(
                    Receipt.due_type == "maintenance", Receipt.due_id.in_(due_ids)
                )
            )
        ).scalars().all()
        receipts_by_due = {r.due_id: r for r in receipt_rows}

    items: list[CollectionReportRow] = []
    total_due = Decimal("0.00")
    total_paid = Decimal("0.00")
    total_pending = Decimal("0.00")
    total_overdue = Decimal("0.00")

    for due, flat_number in rows:
        payment = payments_by_due.get(due.id)
        receipt = receipts_by_due.get(due.id)
        items.append(
            CollectionReportRow(
                flat_number=flat_number,
                owner_names=owner_names.get(due.flat_id, []),
                resident_type=cast(Literal["owner", "tenant"], due.assigned_to_type),
                resident_name=due.assigned_to_name_snapshot,
                amount_due=due.amount,
                status=cast(Literal["paid", "pending", "overdue"], due.status),
                payment_date=payment.payment_date if payment is not None else None,
                payment_mode=(
                    cast(Literal["cash", "bank_transfer", "cheque"], payment.payment_mode)
                    if payment is not None
                    else None
                ),
                reference_number=payment.reference_number if payment is not None else None,
                receipt_number=receipt.receipt_number if receipt is not None else None,
            )
        )
        total_due += due.amount
        if due.status == "paid":
            total_paid += payment.amount_received if payment is not None else due.amount
        elif due.status == "pending":
            total_pending += due.amount
        elif due.status == "overdue":
            total_overdue += due.amount

    return CollectionReportResponse(
        tower_id=tower_id,
        billing_cycle_id=billing_cycle_id,
        billing_month=cycle.month,
        billing_year=cycle.year,
        generated_at=datetime.now(),
        items=items,
        totals={
            "total_due": total_due,
            "total_paid": total_paid,
            "total_pending": total_pending,
            "total_overdue": total_overdue,
        },
    )


# --------------------------------------------------------------------------------------------
# 2.2 Outstanding dues report
# --------------------------------------------------------------------------------------------


async def count_outstanding_dues_rows(db: AsyncSession, *, tower_id: UUID) -> int:
    maintenance_count = (
        await db.scalar(
            select(func.count())
            .select_from(MaintenanceDue)
            .where(MaintenanceDue.tower_id == tower_id, MaintenanceDue.status == "overdue")
        )
        or 0
    )
    special_count = (
        await db.scalar(
            select(func.count())
            .select_from(SpecialCollectionDue)
            .where(
                SpecialCollectionDue.tower_id == tower_id,
                SpecialCollectionDue.status == "overdue",
            )
        )
        or 0
    )
    return maintenance_count + special_count


async def build_outstanding_dues_report(
    db: AsyncSession, *, tower_id: UUID, as_of_date: date
) -> OutstandingDuesReportResponse:
    maintenance_rows = (
        await db.execute(
            select(MaintenanceDue, Flat.flat_number, BillingCycle.grace_period_days_snapshot)
            .join(Flat, Flat.id == MaintenanceDue.flat_id)
            .join(BillingCycle, BillingCycle.id == MaintenanceDue.billing_cycle_id)
            .where(MaintenanceDue.tower_id == tower_id, MaintenanceDue.status == "overdue")
        )
    ).all()
    flat_ids = [due.flat_id for due, _, _ in maintenance_rows]
    owner_names = await _owner_names_by_flat(db, flat_ids)

    items: list[OutstandingDueRow] = []
    for due, flat_number, grace_period_days in maintenance_rows:
        days_overdue = max(
            0, (as_of_date - (due.due_date + timedelta(days=grace_period_days))).days
        )
        items.append(
            OutstandingDueRow(
                flat_number=flat_number,
                due_type="maintenance",
                owner_names=owner_names.get(due.flat_id, []),
                resident_name=due.assigned_to_name_snapshot,
                amount_due=due.amount,
                due_date=due.due_date,
                grace_period_days=grace_period_days,
                days_overdue=days_overdue,
            )
        )

    special_rows = (
        await db.execute(
            select(SpecialCollectionDue).where(
                SpecialCollectionDue.tower_id == tower_id,
                SpecialCollectionDue.status == "overdue",
            )
        )
    ).scalars().all()
    for due in special_rows:
        # No grace-period concept exists for special-collection dues (see
        # `app/models/special_collection_due.py` — no such column, and Module 4 never models
        # one): `grace_period_days=0`, so `days_overdue` is simply `as_of_date - due_date`,
        # floored at 0. Documented decision, not an oversight — see this build's report.
        days_overdue = max(0, (as_of_date - due.due_date).days)
        items.append(
            OutstandingDueRow(
                flat_number=due.flat_number,
                due_type="special_collection",
                owner_names=[due.owner_name],
                resident_name=due.owner_name,
                amount_due=due.amount,
                due_date=due.due_date,
                grace_period_days=0,
                days_overdue=days_overdue,
            )
        )

    items.sort(key=lambda r: (r.flat_number, r.due_date))
    total_outstanding = sum((r.amount_due for r in items), Decimal("0.00"))

    return OutstandingDuesReportResponse(
        tower_id=tower_id, as_of_date=as_of_date, items=items, total_outstanding=total_outstanding
    )


# --------------------------------------------------------------------------------------------
# 2.3 Expenditure report
# --------------------------------------------------------------------------------------------


def _expenditure_filters(tower_id: UUID, period_start: date, period_end: date) -> list:
    return [
        Expenditure.tower_id == tower_id,
        Expenditure.expenditure_date >= period_start,
        Expenditure.expenditure_date <= period_end,
        Expenditure.deactivated_at.is_(None),
    ]


async def count_expenditure_rows(
    db: AsyncSession, *, tower_id: UUID, period_start: date, period_end: date
) -> int:
    return (
        await db.scalar(
            select(func.count())
            .select_from(Expenditure)
            .where(*_expenditure_filters(tower_id, period_start, period_end))
        )
        or 0
    )


async def build_expenditure_report(
    db: AsyncSession, *, tower_id: UUID, period_start: date, period_end: date
) -> ExpenditureReportResponse:
    rows = (
        (
            await db.execute(
                select(Expenditure)
                .where(*_expenditure_filters(tower_id, period_start, period_end))
                .order_by(Expenditure.expenditure_date.asc(), Expenditure.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    items = [
        ExpenditureReportRow(
            date=e.expenditure_date,
            category=cast(
                Literal["cleaning", "security", "repairs", "utilities", "other"], e.category
            ),
            description=e.description,
            vendor_payee=e.vendor_payee_name,
            amount=e.amount,
            payment_mode=e.payment_mode,
            has_attachment=e.attachment_s3_key is not None,
        )
        for e in rows
    ]

    category_rows = (
        await db.execute(
            select(Expenditure.category, func.coalesce(func.sum(Expenditure.amount), 0))
            .where(*_expenditure_filters(tower_id, period_start, period_end))
            .group_by(Expenditure.category)
        )
    ).all()
    category_totals = [
        CategoryTotal(category=category, total=Decimal(total)) for category, total in category_rows
    ]
    grand_total = sum((c.total for c in category_totals), Decimal("0.00"))

    return ExpenditureReportResponse(
        tower_id=tower_id,
        period_start=period_start,
        period_end=period_end,
        items=items,
        category_totals=category_totals,
        grand_total=grand_total,
    )


# --------------------------------------------------------------------------------------------
# 2.4 Collection vs expenditure summary
# --------------------------------------------------------------------------------------------


def resolve_period(
    *, period_type: Literal["month", "financial_year"], month: int | None, year: int
) -> tuple[date, date, str]:
    if period_type == "month":
        if month is None:
            raise AppError(
                422,
                "VALIDATION_ERROR",
                "month is required when period_type=month.",
                field_errors={"month": "required when period_type=month"},
            )
        period_start, period_end = month_bounds(month, year)
        period_label = f"{MONTH_NAMES[month]} {year}"
    else:
        period_start, period_end = financial_year_bounds(year)
        period_label = f"FY {year}-{str(year + 1)[2:]}"
    return period_start, period_end, period_label


async def count_collection_vs_expenditure_rows(
    db: AsyncSession, *, tower_id: UUID, period_start: date, period_end: date
) -> int:
    """This report is a single summary object, not a list — its "row count" is the number of
    expenditure categories it breaks down (always small, never realistically >5000), so the
    export threshold check is effectively a no-op guard here (documented decision, see build
    report) rather than a meaningful sync/async split."""
    rows = (
        await db.scalar(
            select(func.count(func.distinct(Expenditure.category))).where(
                *_expenditure_filters(tower_id, period_start, period_end)
            )
        )
        or 0
    )
    return max(rows, 1)


async def build_collection_vs_expenditure_report(
    db: AsyncSession,
    *,
    tower_id: UUID,
    period_type: Literal["month", "financial_year"],
    month: int | None,
    year: int,
) -> CollectionVsExpenditureResponse:
    period_start, period_end, period_label = resolve_period(
        period_type=period_type, month=month, year=year
    )

    maintenance_collected = await db.scalar(
        select(func.coalesce(func.sum(Payment.amount_received), 0)).where(
            Payment.tower_id == tower_id,
            Payment.due_type == "maintenance",
            Payment.payment_date >= period_start,
            Payment.payment_date <= period_end,
        )
    ) or Decimal("0.00")
    special_collection_collected = await db.scalar(
        select(func.coalesce(func.sum(Payment.amount_received), 0)).where(
            Payment.tower_id == tower_id,
            Payment.due_type == "special_collection",
            Payment.payment_date >= period_start,
            Payment.payment_date <= period_end,
        )
    ) or Decimal("0.00")
    maintenance_collected = Decimal(maintenance_collected)
    special_collection_collected = Decimal(special_collection_collected)
    total_collected = maintenance_collected + special_collection_collected

    category_rows = (
        await db.execute(
            select(Expenditure.category, func.coalesce(func.sum(Expenditure.amount), 0))
            .where(*_expenditure_filters(tower_id, period_start, period_end))
            .group_by(Expenditure.category)
        )
    ).all()
    expenditure_by_category = [
        CategoryTotal(category=category, total=Decimal(total)) for category, total in category_rows
    ]
    total_expenditure = sum((c.total for c in expenditure_by_category), Decimal("0.00"))

    return CollectionVsExpenditureResponse(
        tower_id=tower_id,
        period_label=period_label,
        maintenance_collected=maintenance_collected,
        special_collection_collected=special_collection_collected,
        total_collected=total_collected,
        total_expenditure=total_expenditure,
        net=total_collected - total_expenditure,
        expenditure_by_category=expenditure_by_category,
    )


# --------------------------------------------------------------------------------------------
# 2.5 Tenant register
# --------------------------------------------------------------------------------------------


async def count_tenant_register_rows(
    db: AsyncSession, *, tower_id: UUID, flat_id: UUID | None = None
) -> int:
    filters = [Flat.tower_id == tower_id]
    if flat_id is not None:
        filters.append(Flat.id == flat_id)
    return (
        await db.scalar(
            select(func.count())
            .select_from(Tenant)
            .join(Flat, Flat.id == Tenant.flat_id)
            .where(*filters)
        )
        or 0
    )


async def build_tenant_register_report(
    db: AsyncSession, *, tower_id: UUID, flat_id: UUID | None = None
) -> TenantRegisterResponse:
    filters = [Flat.tower_id == tower_id]
    if flat_id is not None:
        filters.append(Flat.id == flat_id)
    rows = (
        await db.execute(
            select(Tenant, Flat.flat_number)
            .join(Flat, Flat.id == Tenant.flat_id)
            .where(*filters)
            .order_by(Flat.flat_number.asc(), Tenant.lease_start.asc())
        )
    ).all()
    items = [
        TenantRegisterRow(
            flat_number=flat_number,
            tenant_name=tenant.full_name,
            phone_number=tenant.phone,
            email=tenant.email,
            lease_start=tenant.lease_start,
            lease_end=tenant.lease_end,
            is_current=tenant.is_active,
        )
        for tenant, flat_number in rows
    ]
    return TenantRegisterResponse(tower_id=tower_id, items=items)


# --------------------------------------------------------------------------------------------
# Owner-portal helper — per-flat due history (backend.md §3.2 `OwnerFlatDashboardResponse`)
# --------------------------------------------------------------------------------------------


async def build_collection_rows_for_flat(
    db: AsyncSession, *, flat_id: UUID
) -> list[CollectionReportRow]:
    """Every `maintenance_dues` row for one flat, most recent `due_date` first — reuses the
    exact same `CollectionReportRow` shape as the tower-wide collection report (backend.md
    §2.1) so the owner dashboard's `current_due`/`payment_history` fields need no separate
    schema. `owner_names` reflects the flat's *current* active owners regardless of which
    cycle a given due belongs to (mirrors `build_collection_report`'s own behaviour)."""
    flat = await db.get(Flat, flat_id)
    if flat is None:
        return []

    rows = (
        await db.execute(
            select(MaintenanceDue)
            .where(MaintenanceDue.flat_id == flat_id)
            .order_by(MaintenanceDue.due_date.desc(), MaintenanceDue.created_at.desc())
        )
    ).scalars().all()
    if not rows:
        return []

    owner_names = (await _owner_names_by_flat(db, [flat_id])).get(flat_id, [])
    due_ids = [due.id for due in rows]

    payment_rows = (
        await db.execute(
            select(Payment).where(Payment.due_type == "maintenance", Payment.due_id.in_(due_ids))
        )
    ).scalars().all()
    payments_by_due = {p.due_id: p for p in payment_rows}

    receipt_rows = (
        await db.execute(
            select(Receipt).where(Receipt.due_type == "maintenance", Receipt.due_id.in_(due_ids))
        )
    ).scalars().all()
    receipts_by_due = {r.due_id: r for r in receipt_rows}

    items: list[CollectionReportRow] = []
    for due in rows:
        payment = payments_by_due.get(due.id)
        receipt = receipts_by_due.get(due.id)
        items.append(
            CollectionReportRow(
                flat_number=flat.flat_number,
                owner_names=owner_names,
                resident_type=cast(Literal["owner", "tenant"], due.assigned_to_type),
                resident_name=due.assigned_to_name_snapshot,
                amount_due=due.amount,
                status=cast(Literal["paid", "pending", "overdue"], due.status),
                payment_date=payment.payment_date if payment is not None else None,
                payment_mode=(
                    cast(Literal["cash", "bank_transfer", "cheque"], payment.payment_mode)
                    if payment is not None
                    else None
                ),
                reference_number=payment.reference_number if payment is not None else None,
                receipt_number=receipt.receipt_number if receipt is not None else None,
            )
        )
    return items
