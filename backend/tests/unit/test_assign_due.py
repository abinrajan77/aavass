"""backend.md §8.1 / §5 — `assign_due()` unit tests, exercised directly against the
`FlatRead`/`TenantRead`/`OwnerRead` dataclasses (`app.services.flats_service`) with no DB
needed — these are plain in-memory objects, not ORM rows."""

from uuid import uuid4

import pytest

from app.services.billing_cycle import DueGenerationError, assign_due
from app.services.flats_service import FlatRead, OwnerRead, TenantRead


def _flat(**overrides) -> FlatRead:
    defaults = {
        "id": uuid4(),
        "flat_number": "101",
        "carpet_area": None,
        "occupancy_status": "owner_occupied",
        "current_tenant": None,
        "primary_owner": OwnerRead(id=uuid4(), full_name="Asha Rao"),
    }
    defaults.update(overrides)
    return FlatRead(**defaults)


@pytest.mark.asyncio
async def test_tenant_occupied_flat_with_active_tenant_assigns_to_tenant():
    tenant = TenantRead(id=uuid4(), full_name="Ravi Kumar")
    flat = _flat(occupancy_status="tenant_occupied", current_tenant=tenant)

    assigned_to_type, assigned_to_id, assigned_to_name = await assign_due(flat)

    assert assigned_to_type == "tenant"
    assert assigned_to_id == tenant.id
    assert assigned_to_name == tenant.full_name


@pytest.mark.asyncio
async def test_owner_occupied_flat_assigns_to_primary_owner():
    owner = OwnerRead(id=uuid4(), full_name="Asha Rao")
    flat = _flat(occupancy_status="owner_occupied", primary_owner=owner)

    assigned_to_type, assigned_to_id, assigned_to_name = await assign_due(flat)

    assert assigned_to_type == "owner"
    assert assigned_to_id == owner.id
    assert assigned_to_name == owner.full_name


@pytest.mark.asyncio
async def test_vacant_flat_assigns_to_primary_owner():
    """overview.md edge case 11 — vacant flats fall into the same branch as owner-occupied."""
    owner = OwnerRead(id=uuid4(), full_name="Asha Rao")
    flat = _flat(occupancy_status="vacant", current_tenant=None, primary_owner=owner)

    assigned_to_type, assigned_to_id, assigned_to_name = await assign_due(flat)

    assert assigned_to_type == "owner"
    assert assigned_to_id == owner.id


@pytest.mark.asyncio
async def test_tenant_occupied_flat_with_no_active_tenant_falls_back_to_owner():
    """`occupancy_status == 'tenant_occupied'` but `current_tenant is None` (e.g. Module 2
    data lag) is not an error — it falls through to the owner branch just like vacant."""
    owner = OwnerRead(id=uuid4(), full_name="Asha Rao")
    flat = _flat(occupancy_status="tenant_occupied", current_tenant=None, primary_owner=owner)

    assigned_to_type, _, _ = await assign_due(flat)

    assert assigned_to_type == "owner"


@pytest.mark.asyncio
async def test_no_primary_owner_raises_due_generation_error():
    """overview.md edge case 12 — a flat with no owner flagged `is_primary_contact` fails
    generation for that flat specifically, with a NO_PRIMARY_OWNER reason."""
    flat_id = uuid4()
    flat = _flat(id=flat_id, occupancy_status="owner_occupied", primary_owner=None)

    with pytest.raises(DueGenerationError) as exc_info:
        await assign_due(flat)

    assert exc_info.value.flat_id == flat_id
    assert exc_info.value.reason == "NO_PRIMARY_OWNER"
