"""Pydantic-level tests for tenant schemas — `specs/02-flat-owner-tenant/backend.md` unit test
plan: date-ordering validation and the required, no-default `occupancy_status` on vacate must
both fail before ever reaching the DB/service layer."""

import pytest
from pydantic import ValidationError

from app.schemas.tenant import TenantCreate, TenantVacate


def test_tenant_create_lease_end_before_lease_start_raises_value_error():
    with pytest.raises(ValidationError) as exc_info:
        TenantCreate(
            full_name="Tom Tenant",
            phone="9123456780",
            lease_start="2024-06-01",
            lease_end="2024-01-01",
        )
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("lease_end",) for e in errors)


def test_tenant_create_allows_lease_end_on_or_after_lease_start():
    tenant = TenantCreate(
        full_name="Tom Tenant",
        phone="9123456780",
        lease_start="2024-01-01",
        lease_end="2024-01-01",
    )
    assert tenant.lease_end == tenant.lease_start


def test_tenant_create_allows_missing_lease_end():
    tenant = TenantCreate(full_name="Tom Tenant", phone="9123456780", lease_start="2024-01-01")
    assert tenant.lease_end is None


def test_tenant_vacate_requires_occupancy_status():
    with pytest.raises(ValidationError):
        TenantVacate(vacated_date="2024-06-01")  # type: ignore[call-arg]


def test_tenant_vacate_rejects_tenant_occupied_as_target_status():
    with pytest.raises(ValidationError):
        TenantVacate(vacated_date="2024-06-01", occupancy_status="tenant_occupied")


def test_tenant_vacate_accepts_valid_statuses():
    for status in ("owner_occupied", "vacant"):
        vacate = TenantVacate(vacated_date="2024-06-01", occupancy_status=status)
        assert vacate.occupancy_status == status
