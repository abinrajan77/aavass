"""The shared `record_payment()` service function (backend.md §6.5) — the exact integration
point Module 4 depends on. Module 4's special-collection `mark-paid` endpoint is a thin wrapper
that calls this same function with `due_type="special_collection"`; it must not reimplement any
of the logic below (`00-architecture-and-standards.md` §7).

Module 3 does not import Module 4's tables (the dependency direction stays one-way: Module 4
depends on Module 3, not the reverse). Instead, `register_due_resolver()` /
`register_owner_name_resolver()` let Module 4 plug its `special_collection_dues` /
`special_collections` lookups into this function's dispatch tables at import time, without this
module ever needing to `import` anything from `04-special-collections-expenditure`.
"""

from collections.abc import Awaitable, Callable
from datetime import date
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.association_member import AssociationMember
from app.models.billing_cycle import BillingCycle
from app.models.maintenance_due import MaintenanceDue
from app.models.owner import Owner
from app.models.payment import Payment
from app.models.receipt import Receipt
from app.models.user import User
from app.services.audit import write_audit_log
from app.services.receipts import next_receipt_number, render_and_upload_receipt

_MONTH_NAMES = [
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

# `...` (rather than a precise positional signature) because real resolvers take keyword-only
# `due_id`/`tower_id` params and operate on due_type-specific row types (`MaintenanceDue` here,
# a Module 4 row type for "special_collection") — there is no single concrete signature that
# describes every registered resolver, by design.
DueResolver = Callable[..., Awaitable[Any]]
OwnerNameResolver = Callable[..., Awaitable[str]]
LabelResolver = Callable[..., Awaitable[str]]


async def _resolve_maintenance_due(
    db: AsyncSession, *, due_id: UUID, tower_id: UUID
) -> MaintenanceDue:
    due = await db.scalar(
        select(MaintenanceDue).where(
            MaintenanceDue.id == due_id, MaintenanceDue.tower_id == tower_id
        )
    )
    if due is None:
        raise AppError(404, "DUE_NOT_FOUND", "Maintenance due not found.")
    return due


async def _maintenance_billing_period_label(db: AsyncSession, due: MaintenanceDue) -> str:
    cycle = await db.get(BillingCycle, due.billing_cycle_id)
    assert cycle is not None, f"billing_cycle {due.billing_cycle_id} must exist (FK-enforced)"
    return f"{_MONTH_NAMES[cycle.month - 1]} {cycle.year}"


async def _maintenance_owner_name(db: AsyncSession, due: MaintenanceDue) -> str:
    owner = await db.get(Owner, due.primary_owner_id_snapshot)
    return owner.full_name if owner is not None else "Unknown Owner"


# Dispatch tables keyed by `due_type`. Module 4 registers "special_collection" entries into
# these at its own import time (see 04-special-collections-expenditure/backend.md's "Reuse of
# Module 3 payment/receipt flow").
_DUE_RESOLVERS: dict[str, DueResolver] = {"maintenance": _resolve_maintenance_due}
_LABEL_RESOLVERS: dict[str, LabelResolver] = {"maintenance": _maintenance_billing_period_label}
_OWNER_NAME_RESOLVERS: dict[str, OwnerNameResolver] = {"maintenance": _maintenance_owner_name}


def register_due_resolver(due_type: str, resolver: DueResolver) -> None:
    _DUE_RESOLVERS[due_type] = resolver


def register_label_resolver(due_type: str, resolver: LabelResolver) -> None:
    _LABEL_RESOLVERS[due_type] = resolver


def register_owner_name_resolver(due_type: str, resolver: OwnerNameResolver) -> None:
    _OWNER_NAME_RESOLVERS[due_type] = resolver


async def _resolve_due(db: AsyncSession, due_type: str, due_id: UUID, tower_id: UUID):
    resolver = _DUE_RESOLVERS.get(due_type)
    if resolver is None:
        raise AppError(422, "VALIDATION_ERROR", f"Unknown due_type '{due_type}'.")
    return await resolver(db, due_id=due_id, tower_id=tower_id)


async def record_payment(
    db: AsyncSession,
    *,
    tower_id: UUID,
    due_type: Literal["maintenance", "special_collection"],
    due_id: UUID,
    payment_date: date,
    amount_received: Decimal,
    payment_mode: Literal["cash", "bank_transfer", "cheque"],
    reference_number: str | None,
    recorded_by: AssociationMember,
) -> Receipt:
    # 1. Resolve the due row by due_type, scoped to tower_id; 404 if not found in this tower,
    #    409 DUE_ALREADY_PAID if status='paid'.
    due = await _resolve_due(db, due_type, due_id, tower_id)
    if due.status == "paid":
        raise AppError(409, "DUE_ALREADY_PAID", "This due has already been marked as paid.")

    # 2. Insert Payment (single transaction with everything below).
    payment = Payment(
        tower_id=tower_id,
        due_type=due_type,
        due_id=due_id,
        payment_date=payment_date,
        amount_received=amount_received,
        payment_mode=payment_mode,
        reference_number=reference_number,
        recorded_by=recorded_by.id,
    )
    db.add(payment)
    await db.flush()

    # 3. Transition the due's own status column to 'paid' — this function owns this write
    #    regardless of which module's table `due` belongs to (Module 4 grants this function
    #    the necessary DB access for special_collection_dues).
    due.status = "paid"

    # 4. Resolve billing_period_label per due_type.
    label_resolver = _LABEL_RESOLVERS.get(due_type)
    if label_resolver is None:
        raise AppError(422, "VALIDATION_ERROR", f"Unknown due_type '{due_type}'.")
    label = await label_resolver(db, due)

    # Primary owner's name at receipt-generation time — always from the due's frozen
    # `primary_owner_id_snapshot`-equivalent, never from `assigned_to_id`, even when the payer
    # was the tenant (overview.md edge case 4; backend.md §8.3 regression list).
    owner_name_resolver = _OWNER_NAME_RESOLVERS.get(due_type)
    if owner_name_resolver is None:
        raise AppError(422, "VALIDATION_ERROR", f"Unknown due_type '{due_type}'.")
    owner_name = await owner_name_resolver(db, due)

    # 5. Render PDF, upload to S3, get next receipt_number (row-locked, one sequence per tower
    #    shared across due_type).
    receipt_number = await next_receipt_number(db, tower_id)
    pdf_s3_key = await render_and_upload_receipt(
        tower_id=tower_id,
        label=label,
        receipt_number=receipt_number,
        owner_name=owner_name,
        amount=amount_received,
        payment_date=payment_date,
        payment_mode=payment_mode,
    )

    receipt = Receipt(
        tower_id=tower_id,
        due_type=due_type,
        due_id=due_id,
        payment_id=payment.id,
        receipt_number=receipt_number,
        owner_name_snapshot=owner_name,
        billing_period_label=label,
        pdf_s3_key=pdf_s3_key,
    )
    db.add(receipt)

    # 6. Audit log (action="payment_recorded"), same transaction.
    actor = await db.get(User, recorded_by.user_id)
    await write_audit_log(
        db,
        actor=actor,
        tower_id=tower_id,
        action="payment_recorded",
        entity_type=due_type,
        entity_id=due_id,
        before={"status": "pending"},
        after={"status": "paid"},
    )
    await db.commit()
    await db.refresh(receipt)
    return receipt
