"""Tenant Register — backend.md §2.5, overview.md acceptance criterion 5."""

from datetime import date
from uuid import uuid4

import pytest

from tests.factories import (
    DEFAULT_PASSWORD,
    make_association_member,
    make_complex,
    make_flat,
    make_role,
    make_tenant,
    make_tower,
    make_user,
)


async def _login(client, email, password=DEFAULT_PASSWORD):
    return await client.post("/api/v1/auth/login", json={"email": email, "password": password})


async def _setup_reports_admin(db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    role = await make_role(
        db_session, tower_id=tower.id, permission_codes=["VIEW_REPORTS", "VIEW_TOWER_DATA"]
    )
    user = await make_user(db_session, email=f"reports-admin-{uuid4()}@example.com")
    member = await make_association_member(
        db_session, tower_id=tower.id, user_id=user.id, role_id=role.id
    )
    await db_session.commit()
    return tower, user, member


@pytest.mark.asyncio
async def test_tenant_register_includes_current_and_past_ordered(client, db_session):
    tower, user, _member = await _setup_reports_admin(db_session)

    flat_a = await make_flat(db_session, tower_id=tower.id, flat_number="102")
    flat_b = await make_flat(db_session, tower_id=tower.id, flat_number="101")

    await make_tenant(
        db_session, flat_id=flat_a.id, full_name="Current Tenant A",
        lease_start=date(2025, 1, 1), is_active=True,
    )
    await make_tenant(
        db_session, flat_id=flat_b.id, full_name="Past Tenant B1",
        lease_start=date(2023, 1, 1), lease_end=date(2024, 1, 1), is_active=False,
    )
    await make_tenant(
        db_session, flat_id=flat_b.id, full_name="Current Tenant B2",
        lease_start=date(2024, 6, 1), is_active=True,
    )
    await db_session.commit()

    await _login(client, user.email)
    resp = await client.get(f"/api/v1/towers/{tower.id}/reports/tenant-register")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 3

    # Ordered by flat_number then lease_start ascending: flat 101 (2 rows) before flat 102.
    flat_numbers = [row["flat_number"] for row in body["items"]]
    assert flat_numbers == ["101", "101", "102"]
    assert body["items"][0]["tenant_name"] == "Past Tenant B1"
    assert body["items"][0]["is_current"] is False
    assert body["items"][1]["tenant_name"] == "Current Tenant B2"
    assert body["items"][1]["is_current"] is True
    assert body["items"][2]["is_current"] is True
