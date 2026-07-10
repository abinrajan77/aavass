"""FlatOwnership business logic: adding an owner to a flat, flipping the primary contact, and
removing a co-owner — all guarding the "exactly one primary owner per flat" invariant
(`uq_flat_primary_contact_active`) and the "at least one active owner" / "primary contact
required before removal" edge cases from `specs/02-flat-owner-tenant/overview.md`.

The primary-contact flip is always sequenced as "demote the old row, then promote the new
one" as two separate `UPDATE`s inside the same transaction — by the time the second statement
runs, the first row no longer matches the partial unique index's predicate
(`date_to IS NULL AND is_primary_contact`), so there is never a window where two active rows
both have `is_primary_contact=True`.
"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.flat import Flat
from app.models.flat_ownership import FlatOwnership
from app.models.owner import Owner
from app.models.user import User
from app.schemas.owner import (
    FlatOwnershipCreateRequest,
    FlatOwnershipUpdate,
    OwnerRemoveRequest,
)
from app.services.audit import write_audit_log


async def _get_active_primary(db: AsyncSession, *, flat_id: UUID) -> FlatOwnership | None:
    return await db.scalar(
        select(FlatOwnership).where(
            FlatOwnership.flat_id == flat_id,
            FlatOwnership.date_to.is_(None),
            FlatOwnership.is_primary_contact.is_(True),
        )
    )


async def _count_active_owners(
    db: AsyncSession, *, flat_id: UUID, exclude_ownership_id: UUID | None = None
) -> int:
    stmt = select(func.count()).select_from(FlatOwnership).where(
        FlatOwnership.flat_id == flat_id, FlatOwnership.date_to.is_(None)
    )
    if exclude_ownership_id is not None:
        stmt = stmt.where(FlatOwnership.id != exclude_ownership_id)
    return (await db.scalar(stmt)) or 0


async def add_owner_to_flat(
    db: AsyncSession,
    *,
    flat: Flat,
    payload: FlatOwnershipCreateRequest,
    actor: User,
) -> FlatOwnership:
    if payload.owner_id is not None:
        owner = await db.get(Owner, payload.owner_id)
        if owner is None:
            raise AppError(
                422,
                "VALIDATION_ERROR",
                "Owner not found.",
                field_errors={"owner_id": "No owner exists with this id."},
            )
    else:
        assert payload.full_name is not None  # enforced by the schema's model_validator
        assert payload.phone is not None
        owner = Owner(
            full_name=payload.full_name,
            phone=payload.phone,
            email=payload.email,
            id_number=payload.id_number,
        )
        db.add(owner)
        await db.flush()

    active_owner_count = await _count_active_owners(db, flat_id=flat.id)
    # A flat must always have exactly one primary owner once it has any owner at all — force
    # the very first owner to be primary regardless of the caller-supplied flag.
    make_primary = payload.is_primary_contact or active_owner_count == 0

    if make_primary:
        current_primary = await _get_active_primary(db, flat_id=flat.id)
        if current_primary is not None:
            current_primary.is_primary_contact = False
            await db.flush()

    ownership = FlatOwnership(
        flat_id=flat.id,
        owner_id=owner.id,
        is_primary_contact=make_primary,
        date_from=payload.date_from,
        created_by_user_id=actor.id,
    )
    db.add(ownership)
    await db.flush()

    await write_audit_log(
        db,
        actor=actor,
        tower_id=flat.tower_id,
        action="OWNER_LINKED_TO_FLAT",
        entity_type="FlatOwnership",
        entity_id=ownership.id,
        before=None,
        after={
            "owner_id": str(owner.id),
            "is_primary_contact": ownership.is_primary_contact,
        },
    )
    return ownership


async def flip_primary_contact(
    db: AsyncSession,
    *,
    flat: Flat,
    ownership_id: UUID,
    payload: FlatOwnershipUpdate,
    actor: User,
) -> FlatOwnership:
    ownership = await db.scalar(
        select(FlatOwnership).where(
            FlatOwnership.id == ownership_id,
            FlatOwnership.flat_id == flat.id,
            FlatOwnership.date_to.is_(None),
        )
    )
    if ownership is None:
        raise AppError(404, "OWNERSHIP_NOT_FOUND", "Ownership record not found for this flat.")

    before = {"is_primary_contact": ownership.is_primary_contact}

    if payload.is_primary_contact is True and not ownership.is_primary_contact:
        current_primary = await _get_active_primary(db, flat_id=flat.id)
        if current_primary is not None and current_primary.id != ownership.id:
            current_primary.is_primary_contact = False
            await db.flush()
        ownership.is_primary_contact = True
    elif payload.is_primary_contact is False and ownership.is_primary_contact:
        # Demoting the sole primary contact would leave the flat with zero primary owners
        # while it still has owner(s) — never allowed without atomically nominating a
        # replacement (`new_primary_owner_id`), matching the `.../remove` endpoint's contract.
        remaining = await _count_active_owners(
            db, flat_id=flat.id, exclude_ownership_id=ownership.id
        )
        if remaining == 0:
            raise AppError(
                409,
                "LAST_OWNER_ON_FLAT",
                "Cannot remove primary-contact status; this is the flat's only active owner.",
            )
        if payload.new_primary_owner_id is None:
            raise AppError(
                409,
                "PRIMARY_CONTACT_REQUIRED",
                "Nominate a new primary contact (new_primary_owner_id) atomically with the "
                "demotion.",
            )
        new_primary = await db.scalar(
            select(FlatOwnership).where(
                FlatOwnership.flat_id == flat.id,
                FlatOwnership.owner_id == payload.new_primary_owner_id,
                FlatOwnership.date_to.is_(None),
                FlatOwnership.id != ownership.id,
            )
        )
        if new_primary is None:
            raise AppError(
                422,
                "VALIDATION_ERROR",
                "new_primary_owner_id is not a currently active owner of this flat.",
                field_errors={"new_primary_owner_id": "Not an active owner of this flat."},
            )
        ownership.is_primary_contact = False
        await db.flush()
        new_primary.is_primary_contact = True

    await db.flush()

    await write_audit_log(
        db,
        actor=actor,
        tower_id=flat.tower_id,
        action="OWNERSHIP_PRIMARY_CONTACT_UPDATED",
        entity_type="FlatOwnership",
        entity_id=ownership.id,
        before=before,
        after={"is_primary_contact": ownership.is_primary_contact},
    )
    return ownership


async def remove_owner(
    db: AsyncSession,
    *,
    flat: Flat,
    ownership_id: UUID,
    payload: OwnerRemoveRequest,
    actor: User,
) -> FlatOwnership:
    ownership = await db.scalar(
        select(FlatOwnership).where(
            FlatOwnership.id == ownership_id,
            FlatOwnership.flat_id == flat.id,
            FlatOwnership.date_to.is_(None),
        )
    )
    if ownership is None:
        raise AppError(404, "OWNERSHIP_NOT_FOUND", "Ownership record not found for this flat.")

    other_active = await _count_active_owners(
        db, flat_id=flat.id, exclude_ownership_id=ownership.id
    )
    if other_active == 0:
        raise AppError(
            409,
            "LAST_OWNER_ON_FLAT",
            "A flat must always retain at least one active owner; add a replacement before "
            "removing the last one.",
        )

    new_primary: FlatOwnership | None = None
    if ownership.is_primary_contact:
        if payload.new_primary_owner_id is None:
            raise AppError(
                409,
                "PRIMARY_CONTACT_REQUIRED",
                "This owner is the primary contact; nominate new_primary_owner_id atomically "
                "with the removal.",
            )
        new_primary = await db.scalar(
            select(FlatOwnership).where(
                FlatOwnership.flat_id == flat.id,
                FlatOwnership.owner_id == payload.new_primary_owner_id,
                FlatOwnership.date_to.is_(None),
                FlatOwnership.id != ownership.id,
            )
        )
        if new_primary is None:
            raise AppError(
                422,
                "VALIDATION_ERROR",
                "new_primary_owner_id is not a currently active owner of this flat.",
                field_errors={"new_primary_owner_id": "Not an active owner of this flat."},
            )

    before = {"date_to": None, "is_primary_contact": ownership.is_primary_contact}
    ownership.date_to = payload.effective_date
    await db.flush()

    if new_primary is not None:
        new_primary.is_primary_contact = True
        await db.flush()

    await write_audit_log(
        db,
        actor=actor,
        tower_id=flat.tower_id,
        action="OWNER_REMOVED_FROM_FLAT",
        entity_type="FlatOwnership",
        entity_id=ownership.id,
        before=before,
        after={
            "date_to": ownership.date_to.isoformat(),
            "new_primary_owner_id": str(payload.new_primary_owner_id)
            if payload.new_primary_owner_id
            else None,
        },
    )
    return ownership
