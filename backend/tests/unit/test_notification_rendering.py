"""Unit tests for `app.services.notifications` — backend.md test plan's rendering checks,
exercised directly against the service (not the HTTP route in
`tests/integration/test_notification_preview.py`). Needs `db_session` since template lookup
and resident/owner resolution are real queries, but no HTTP client/auth involved — same
"unit test with a real DB" pattern as `tests/unit/test_occupancy_service.py`."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.errors import AppError
from app.services.notifications import DueContext, build_notification_messages
from tests.factories import make_complex as _make_complex
from tests.factories import (
    make_flat,
    make_flat_ownership,
    make_owner,
    make_tenant,
    make_tower,
)
from tests.factories import make_user as _make_user


def _context(**overrides) -> DueContext:
    defaults = dict(
        tower_id=uuid4(),
        flat_id=uuid4(),
        flat_number="101",
        tower_name="Oak Tower",
        amount=Decimal("2000.00"),
        due_date=date(2026, 7, 10),
        period_label="July 2026",
        occupancy_status="owner_occupied",
    )
    defaults.update(overrides)
    return DueContext(**defaults)


@pytest.mark.asyncio
async def test_tenant_occupied_flat_produces_exactly_two_messages(db_session):
    complex_row = await _make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    creator = await _make_user(db_session, email=f"creator-{uuid4()}@example.com")
    flat = await make_flat(
        db_session, tower_id=tower.id, flat_number="101", occupancy_status="tenant_occupied"
    )
    owner = await make_owner(db_session, full_name="Asha Rao", phone="9000000001")
    await make_flat_ownership(
        db_session, flat_id=flat.id, owner_id=owner.id, created_by_user_id=creator.id,
        is_primary_contact=True,
    )
    tenant = await make_tenant(
        db_session, flat_id=flat.id, full_name="Ravi Kumar", phone="9000000002"
    )
    await db_session.commit()

    context = _context(
        tower_id=tower.id, flat_id=flat.id, tower_name=tower.name,
        occupancy_status="tenant_occupied",
    )
    messages = await build_notification_messages(
        db_session, event="due_generated", context=context
    )

    assert len(messages) == 2
    tenant_msg = next(m for m in messages if m.recipient == "tenant")
    owner_msg = next(m for m in messages if m.recipient == "owner")
    assert tenant_msg.recipient_name == tenant.full_name
    assert tenant_msg.recipient_phone == tenant.phone
    assert "Ravi Kumar" in tenant_msg.message_text
    assert "2000.00" in tenant_msg.message_text
    assert "101" in tenant_msg.message_text
    assert "Oak Tower" in tenant_msg.message_text
    assert owner_msg.recipient_name == owner.full_name
    assert "Ravi Kumar" in owner_msg.message_text  # owner_copy names the resident being billed


@pytest.mark.asyncio
async def test_owner_occupied_flat_produces_exactly_one_message(db_session):
    complex_row = await _make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    creator = await _make_user(db_session, email=f"creator-{uuid4()}@example.com")
    flat = await make_flat(
        db_session, tower_id=tower.id, flat_number="202", occupancy_status="owner_occupied"
    )
    owner = await make_owner(db_session, full_name="Meena Iyer", phone="9000000003")
    await make_flat_ownership(
        db_session, flat_id=flat.id, owner_id=owner.id, created_by_user_id=creator.id,
        is_primary_contact=True,
    )
    await db_session.commit()

    context = _context(
        tower_id=tower.id, flat_id=flat.id, tower_name=tower.name,
        occupancy_status="owner_occupied",
    )
    messages = await build_notification_messages(
        db_session, event="overdue_reminder", context=context
    )

    assert len(messages) == 1
    assert messages[0].recipient == "owner"
    assert messages[0].recipient_name == "Meena Iyer"
    assert "Meena Iyer" in messages[0].message_text


@pytest.mark.asyncio
async def test_missing_resident_raises_422(db_session):
    complex_row = await _make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    flat = await make_flat(
        db_session, tower_id=tower.id, flat_number="303", occupancy_status="vacant"
    )
    await db_session.commit()
    # No FlatOwnership/Tenant created for this flat at all.

    context = _context(
        tower_id=tower.id, flat_id=flat.id, tower_name=tower.name, occupancy_status="vacant"
    )
    with pytest.raises(AppError) as exc_info:
        await build_notification_messages(db_session, event="due_generated", context=context)
    assert exc_info.value.status_code == 422
    assert exc_info.value.error_code == "NO_RESIDENT_RESOLVED"
