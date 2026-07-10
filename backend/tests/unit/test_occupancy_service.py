"""Service-layer tests for `app/services/occupancy.py` — exercised directly (not via HTTP)
against a real DB session, per `specs/02-flat-owner-tenant/backend.md` unit test plan:
"Adding a tenant to a flat with an existing active tenant raises 409 ONE_ACTIVE_TENANT ...
asserts no insert attempted."
"""

from datetime import date

import pytest
from sqlalchemy import func, select

from app.core.errors import AppError
from app.models.tenant import Tenant
from app.schemas.tenant import TenantCreate, TenantVacate
from app.services import occupancy
from tests.factories import make_complex, make_flat, make_tenant, make_tower, make_user


@pytest.mark.asyncio
async def test_create_tenant_transitions_flat_to_tenant_occupied(db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    flat = await make_flat(db_session, tower_id=tower.id)
    actor = await make_user(db_session, email="occupancy-actor@example.com")
    await db_session.flush()

    tenant = await occupancy.create_tenant(
        db_session,
        flat_id=flat.id,
        payload=TenantCreate(
            full_name="First Tenant", phone="9111111111", lease_start=date(2024, 1, 1)
        ),
        actor=actor,
    )
    await db_session.commit()

    assert tenant.is_active is True
    await db_session.refresh(flat)
    assert flat.occupancy_status == "tenant_occupied"


@pytest.mark.asyncio
async def test_create_tenant_raises_one_active_tenant_when_active_exists(db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    flat = await make_flat(db_session, tower_id=tower.id)
    actor = await make_user(db_session, email="occupancy-actor-2@example.com")
    await make_tenant(db_session, flat_id=flat.id, full_name="Existing Tenant")
    await db_session.commit()

    before_count = await db_session.scalar(
        select(func.count()).select_from(Tenant).where(Tenant.flat_id == flat.id)
    )

    with pytest.raises(AppError) as exc_info:
        await occupancy.create_tenant(
            db_session,
            flat_id=flat.id,
            payload=TenantCreate(
                full_name="Second Tenant", phone="9222222222", lease_start=date(2024, 6, 1)
            ),
            actor=actor,
        )
    assert exc_info.value.status_code == 409
    assert exc_info.value.error_code == "ONE_ACTIVE_TENANT"

    after_count = await db_session.scalar(
        select(func.count()).select_from(Tenant).where(Tenant.flat_id == flat.id)
    )
    assert after_count == before_count  # no new row was inserted


@pytest.mark.asyncio
async def test_vacate_tenant_sets_flat_occupancy_status_exactly_as_requested(db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    flat = await make_flat(db_session, tower_id=tower.id, occupancy_status="tenant_occupied")
    tenant = await make_tenant(db_session, flat_id=flat.id)
    actor = await make_user(db_session, email="vacate-actor@example.com")
    await db_session.commit()

    vacated_tenant, updated_flat = await occupancy.vacate_tenant(
        db_session,
        tenant_id=tenant.id,
        flat_id=flat.id,
        payload=TenantVacate(vacated_date=date(2024, 12, 1), occupancy_status="vacant"),
        actor=actor,
    )
    await db_session.commit()

    assert vacated_tenant.is_active is False
    assert vacated_tenant.vacated_at is not None
    # Must be exactly "vacant", never defaulted to "owner_occupied".
    assert updated_flat.occupancy_status == "vacant"


@pytest.mark.asyncio
async def test_vacate_tenant_rejects_already_vacated_tenant(db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    flat = await make_flat(db_session, tower_id=tower.id)
    tenant = await make_tenant(db_session, flat_id=flat.id, is_active=False)
    actor = await make_user(db_session, email="vacate-actor-2@example.com")
    await db_session.commit()

    with pytest.raises(AppError) as exc_info:
        await occupancy.vacate_tenant(
            db_session,
            tenant_id=tenant.id,
            flat_id=flat.id,
            payload=TenantVacate(vacated_date=date(2024, 12, 1), occupancy_status="vacant"),
            actor=actor,
        )
    assert exc_info.value.status_code == 409
    assert exc_info.value.error_code == "IMMUTABLE_RECORD"
