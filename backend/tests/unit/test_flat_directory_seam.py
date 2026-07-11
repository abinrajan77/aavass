"""Test for the Module 2 integration seam (`app/services/flat_directory.py`) —
`RealFlatDirectory` is the production implementation backed by Module 2's real
`flats`/`flat_ownerships`/`owners` tables; this locks in the "active flat, primary owner via
FlatOwnership, no-owner flats reported as None rather than fabricated" contract
`app.services.special_collection` depends on (backend.md test plan item 3, "NO_ACTIVE_OWNER
skip path")."""

import pytest

from app.services.flat_directory import RealFlatDirectory
from tests.factories import (
    make_complex,
    make_flat,
    make_flat_ownership,
    make_owner,
    make_tower,
    make_user,
)


@pytest.mark.asyncio
async def test_real_flat_directory_returns_active_flats_with_primary_owner(db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    user = await make_user(db_session, email="flat-directory-creator@example.com")

    owned_flat = await make_flat(db_session, tower_id=tower.id, flat_number="101")
    owner = await make_owner(db_session, full_name="Asha Rao")
    await make_flat_ownership(
        db_session, flat_id=owned_flat.id, owner_id=owner.id, created_by_user_id=user.id
    )

    await make_flat(db_session, tower_id=tower.id, flat_number="102")
    await db_session.commit()

    directory = RealFlatDirectory(db=db_session)
    records = await directory.list_active_flats(tower_id=tower.id)
    by_flat_number = {r.flat_number: r for r in records}

    assert len(records) == 2
    assert by_flat_number["101"].owner_id == owner.id
    assert by_flat_number["101"].owner_name == "Asha Rao"
    assert by_flat_number["102"].owner_id is None
    assert by_flat_number["102"].owner_name is None


@pytest.mark.asyncio
async def test_real_flat_directory_excludes_deactivated_flats(db_session):
    from app.models.flat import Flat

    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    active_flat = await make_flat(db_session, tower_id=tower.id, flat_number="201")
    deactivated_flat = await make_flat(db_session, tower_id=tower.id, flat_number="202")
    deactivated_flat.deactivated_at = active_flat.created_at
    await db_session.flush()
    await db_session.commit()

    directory = RealFlatDirectory(db=db_session)
    records = await directory.list_active_flats(tower_id=tower.id)

    assert {r.flat_number for r in records} == {"201"}
    assert await db_session.get(Flat, deactivated_flat.id) is not None  # sanity: still exists
