"""Service-layer tests for `app/services/ownership.py` — `specs/02-flat-owner-tenant/
backend.md` unit test plan: the primary-contact flip must never leave two active rows both
`is_primary_contact=True` (verified via a `SELECT COUNT(*)` assertion post-commit), and the
LAST_OWNER_ON_FLAT / PRIMARY_CONTACT_REQUIRED edge cases must be enforced before any write.
"""

from datetime import date

import pytest
from sqlalchemy import func, select

from app.core.errors import AppError
from app.models.flat_ownership import FlatOwnership
from app.schemas.owner import (
    FlatOwnershipCreateRequest,
    FlatOwnershipUpdate,
    OwnerRemoveRequest,
)
from app.services import ownership
from tests.factories import (
    make_complex,
    make_flat,
    make_flat_ownership,
    make_owner,
    make_tower,
    make_user,
)


async def _count_active_primary(db, flat_id):
    return await db.scalar(
        select(func.count()).select_from(FlatOwnership).where(
            FlatOwnership.flat_id == flat_id,
            FlatOwnership.date_to.is_(None),
            FlatOwnership.is_primary_contact.is_(True),
        )
    )


@pytest.mark.asyncio
async def test_first_owner_added_is_forced_primary_even_if_not_requested(db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    flat = await make_flat(db_session, tower_id=tower.id)
    actor = await make_user(db_session, email="ownership-actor@example.com")
    await db_session.flush()

    row = await ownership.add_owner_to_flat(
        db_session,
        flat=flat,
        payload=FlatOwnershipCreateRequest(
            full_name="First Owner",
            phone="9000000001",
            is_primary_contact=False,
            date_from=date(2024, 1, 1),
        ),
        actor=actor,
    )
    await db_session.commit()

    assert row.is_primary_contact is True
    assert await _count_active_primary(db_session, flat.id) == 1


@pytest.mark.asyncio
async def test_adding_second_primary_owner_atomically_demotes_the_first(db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    flat = await make_flat(db_session, tower_id=tower.id)
    actor = await make_user(db_session, email="ownership-actor-2@example.com")
    owner1 = await make_owner(db_session, full_name="Owner One")
    await make_flat_ownership(
        db_session, flat_id=flat.id, owner_id=owner1.id, created_by_user_id=actor.id
    )
    await db_session.commit()

    row2 = await ownership.add_owner_to_flat(
        db_session,
        flat=flat,
        payload=FlatOwnershipCreateRequest(
            full_name="Owner Two",
            phone="9000000002",
            is_primary_contact=True,
            date_from=date(2024, 2, 1),
        ),
        actor=actor,
    )
    await db_session.commit()

    assert row2.is_primary_contact is True
    # No window where two active rows are both primary — verified post-commit.
    assert await _count_active_primary(db_session, flat.id) == 1


@pytest.mark.asyncio
async def test_flip_primary_contact_atomically_clears_previous_primary(db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    flat = await make_flat(db_session, tower_id=tower.id)
    actor = await make_user(db_session, email="ownership-actor-3@example.com")
    owner1 = await make_owner(db_session, full_name="Primary Owner")
    owner2 = await make_owner(db_session, full_name="Co Owner")
    primary_row = await make_flat_ownership(
        db_session, flat_id=flat.id, owner_id=owner1.id, created_by_user_id=actor.id
    )
    co_owner_row = await make_flat_ownership(
        db_session,
        flat_id=flat.id,
        owner_id=owner2.id,
        created_by_user_id=actor.id,
        is_primary_contact=False,
    )
    await db_session.commit()

    updated = await ownership.flip_primary_contact(
        db_session,
        flat=flat,
        ownership_id=co_owner_row.id,
        payload=FlatOwnershipUpdate(is_primary_contact=True),
        actor=actor,
    )
    await db_session.commit()

    assert updated.is_primary_contact is True
    assert await _count_active_primary(db_session, flat.id) == 1
    await db_session.refresh(primary_row)
    assert primary_row.is_primary_contact is False


@pytest.mark.asyncio
async def test_remove_sole_active_owner_raises_last_owner_on_flat(db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    flat = await make_flat(db_session, tower_id=tower.id)
    actor = await make_user(db_session, email="ownership-actor-4@example.com")
    owner = await make_owner(db_session, full_name="Sole Owner")
    ownership_row = await make_flat_ownership(
        db_session, flat_id=flat.id, owner_id=owner.id, created_by_user_id=actor.id
    )
    await db_session.commit()

    with pytest.raises(AppError) as exc_info:
        await ownership.remove_owner(
            db_session,
            flat=flat,
            ownership_id=ownership_row.id,
            payload=OwnerRemoveRequest(effective_date=date(2024, 6, 1)),
            actor=actor,
        )
    assert exc_info.value.status_code == 409
    assert exc_info.value.error_code == "LAST_OWNER_ON_FLAT"

    await db_session.refresh(ownership_row)
    assert ownership_row.date_to is None


@pytest.mark.asyncio
async def test_remove_primary_owner_without_new_primary_raises_primary_contact_required(
    db_session,
):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    flat = await make_flat(db_session, tower_id=tower.id)
    actor = await make_user(db_session, email="ownership-actor-5@example.com")
    owner1 = await make_owner(db_session, full_name="Primary Owner")
    owner2 = await make_owner(db_session, full_name="Co Owner")
    primary_row = await make_flat_ownership(
        db_session, flat_id=flat.id, owner_id=owner1.id, created_by_user_id=actor.id
    )
    await make_flat_ownership(
        db_session,
        flat_id=flat.id,
        owner_id=owner2.id,
        created_by_user_id=actor.id,
        is_primary_contact=False,
    )
    await db_session.commit()

    with pytest.raises(AppError) as exc_info:
        await ownership.remove_owner(
            db_session,
            flat=flat,
            ownership_id=primary_row.id,
            payload=OwnerRemoveRequest(effective_date=date(2024, 6, 1)),
            actor=actor,
        )
    assert exc_info.value.status_code == 409
    assert exc_info.value.error_code == "PRIMARY_CONTACT_REQUIRED"

    await db_session.refresh(primary_row)
    assert primary_row.date_to is None  # ownership row untouched


@pytest.mark.asyncio
async def test_remove_primary_owner_with_new_primary_succeeds(db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    flat = await make_flat(db_session, tower_id=tower.id)
    actor = await make_user(db_session, email="ownership-actor-6@example.com")
    owner1 = await make_owner(db_session, full_name="Primary Owner")
    owner2 = await make_owner(db_session, full_name="Co Owner")
    primary_row = await make_flat_ownership(
        db_session, flat_id=flat.id, owner_id=owner1.id, created_by_user_id=actor.id
    )
    co_owner_row = await make_flat_ownership(
        db_session,
        flat_id=flat.id,
        owner_id=owner2.id,
        created_by_user_id=actor.id,
        is_primary_contact=False,
    )
    await db_session.commit()

    result = await ownership.remove_owner(
        db_session,
        flat=flat,
        ownership_id=primary_row.id,
        payload=OwnerRemoveRequest(
            effective_date=date(2024, 6, 1), new_primary_owner_id=owner2.id
        ),
        actor=actor,
    )
    await db_session.commit()

    assert result.date_to == date(2024, 6, 1)
    await db_session.refresh(co_owner_row)
    assert co_owner_row.is_primary_contact is True
    assert await _count_active_primary(db_session, flat.id) == 1
