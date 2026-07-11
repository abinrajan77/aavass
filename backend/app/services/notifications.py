"""Notification template rendering — backend.md §4. Consumes due/payment status already
produced by Modules 3/4; never re-derives due amounts/status itself
(`00-architecture-and-standards.md` §7).

Recipient resolution uses the **current** live state (`Flat.occupancy_status`, the active
`Tenant`, the active primary-contact `FlatOwnership`) rather than the due's frozen
`assigned_to_*` snapshot — overview.md's edge case and backend.md §4 step 3 both key the
one-vs-two-message decision off `flats.occupancy_status` *at request time*, which is a live
read, not a generation-time snapshot; this module follows that literally so a preview always
reflects who actually lives there today.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.billing_cycle import BillingCycle
from app.models.flat import Flat
from app.models.flat_ownership import FlatOwnership
from app.models.maintenance_due import MaintenanceDue
from app.models.notification_template import NotificationTemplate
from app.models.owner import Owner
from app.models.special_collection import SpecialCollection
from app.models.special_collection_due import SpecialCollectionDue
from app.models.tenant import Tenant
from app.models.tower import Tower
from app.schemas.notification import NotificationEvent, NotificationMessage
from app.services.reporting import MONTH_NAMES


@dataclass(frozen=True)
class _Recipient:
    name: str
    phone: str


@dataclass(frozen=True)
class DueContext:
    tower_id: UUID
    flat_id: UUID
    flat_number: str
    tower_name: str
    amount: Decimal
    due_date: date
    period_label: str
    occupancy_status: str


async def resolve_due_context(
    db: AsyncSession, *, due_type: str, due_id: UUID
) -> DueContext:
    if due_type == "maintenance":
        due = await db.get(MaintenanceDue, due_id)
        if due is None:
            raise AppError(404, "DUE_NOT_FOUND", "Maintenance due not found.")
        cycle = await db.get(BillingCycle, due.billing_cycle_id)
        assert cycle is not None, f"billing cycle {due.billing_cycle_id} must exist (FK-enforced)"
        period_label = f"{MONTH_NAMES[cycle.month]} {cycle.year}"
        tower_id, flat_id, amount, due_date = due.tower_id, due.flat_id, due.amount, due.due_date
    elif due_type == "special_collection":
        sc_due = await db.get(SpecialCollectionDue, due_id)
        if sc_due is None:
            raise AppError(404, "DUE_NOT_FOUND", "Special collection due not found.")
        collection = await db.get(SpecialCollection, sc_due.special_collection_id)
        assert collection is not None, (
            f"special collection {sc_due.special_collection_id} must exist (FK-enforced)"
        )
        period_label = collection.title
        tower_id = sc_due.tower_id
        flat_id = sc_due.flat_id
        amount = sc_due.amount
        due_date = sc_due.due_date
    else:
        raise AppError(
            422,
            "VALIDATION_ERROR",
            "due_type must be 'maintenance' or 'special_collection'.",
            field_errors={"due_type": "must be 'maintenance' or 'special_collection'"},
        )

    flat = await db.get(Flat, flat_id)
    if flat is None:
        raise AppError(422, "FLAT_NOT_FOUND", "The flat for this due could not be resolved.")
    tower = await db.get(Tower, tower_id)
    assert tower is not None, f"tower {tower_id} must exist (FK-enforced)"

    return DueContext(
        tower_id=tower_id,
        flat_id=flat_id,
        flat_number=flat.flat_number,
        tower_name=tower.name,
        amount=amount,
        due_date=due_date,
        period_label=period_label,
        occupancy_status=flat.occupancy_status,
    )


async def _resolve_recipients(
    db: AsyncSession, *, flat_id: UUID, occupancy_status: str
) -> tuple[_Recipient, _Recipient | None]:
    """Returns `(resident, owner_or_none)`. `resident` is the current active tenant if
    `occupancy_status == 'tenant_occupied'`, else the current active primary-contact owner.
    `owner` is the current active primary-contact owner, only populated (and only relevant)
    when the flat is tenant-occupied — the second, owner-copy message. Raises `422` if the
    flat's own occupancy status can't be backed by a resolvable resident record (overview.md's
    defensive "no resident assigned" edge case)."""
    primary_owner = await db.scalar(
        select(Owner)
        .join(FlatOwnership, FlatOwnership.owner_id == Owner.id)
        .where(
            FlatOwnership.flat_id == flat_id,
            FlatOwnership.date_to.is_(None),
            FlatOwnership.is_primary_contact.is_(True),
        )
        .limit(1)
    )

    if occupancy_status == "tenant_occupied":
        tenant = await db.scalar(
            select(Tenant)
            .where(Tenant.flat_id == flat_id, Tenant.is_active.is_(True))
            .order_by(Tenant.created_at.desc())
            .limit(1)
        )
        if tenant is None or primary_owner is None:
            raise AppError(
                422,
                "NO_RESIDENT_RESOLVED",
                "No resolvable resident/owner for this due's flat.",
            )
        return (
            _Recipient(name=tenant.full_name, phone=tenant.phone),
            _Recipient(name=primary_owner.full_name, phone=primary_owner.phone),
        )

    if primary_owner is None:
        raise AppError(
            422, "NO_RESIDENT_RESOLVED", "No resolvable resident/owner for this due's flat."
        )
    return _Recipient(name=primary_owner.full_name, phone=primary_owner.phone), None


async def _template_text(
    db: AsyncSession, *, event: NotificationEvent, recipient_role: str
) -> str:
    template = await db.scalar(
        select(NotificationTemplate).where(
            NotificationTemplate.event_type == event,
            NotificationTemplate.recipient_role == recipient_role,
            NotificationTemplate.channel == "generic",
            NotificationTemplate.is_active.is_(True),
        )
    )
    assert template is not None, (
        f"notification_templates seed row missing for ({event}, {recipient_role}, generic)"
    )
    return template.template_text


def _render(template_text: str, *, resident_name: str, context: DueContext) -> str:
    return template_text.format(
        resident_name=resident_name,
        flat_number=context.flat_number,
        tower_name=context.tower_name,
        amount=f"{context.amount:.2f}",
        due_date=context.due_date.isoformat(),
        period=context.period_label,
    )


async def build_notification_messages(
    db: AsyncSession, *, event: NotificationEvent, context: DueContext
) -> list[NotificationMessage]:
    resident, owner = await _resolve_recipients(
        db, flat_id=context.flat_id, occupancy_status=context.occupancy_status
    )

    messages: list[NotificationMessage] = []
    resident_template = await _template_text(db, event=event, recipient_role="resident")
    messages.append(
        NotificationMessage(
            recipient="tenant" if context.occupancy_status == "tenant_occupied" else "owner",
            recipient_name=resident.name,
            recipient_phone=resident.phone,
            message_text=_render(resident_template, resident_name=resident.name, context=context),
        )
    )

    if context.occupancy_status == "tenant_occupied":
        assert owner is not None, "owner must be resolved for a tenant-occupied flat"
        owner_copy_template = await _template_text(db, event=event, recipient_role="owner_copy")
        messages.append(
            NotificationMessage(
                recipient="owner",
                recipient_name=owner.name,
                recipient_phone=owner.phone,
                # `{resident_name}` in the owner-copy variant refers to the tenant being
                # informed *about* — the owner is receiving a copy, not addressed as the
                # resident themselves.
                message_text=_render(
                    owner_copy_template, resident_name=resident.name, context=context
                ),
            )
        )

    return messages
