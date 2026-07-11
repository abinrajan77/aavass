"""Expenditure Report — backend.md §2.3, overview.md acceptance criterion 3."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from tests.factories import (
    DEFAULT_PASSWORD,
    make_association_member,
    make_complex,
    make_expenditure,
    make_role,
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
async def test_expenditure_report_itemised_with_category_subtotals(client, db_session):
    tower, user, member = await _setup_reports_admin(db_session)
    await make_expenditure(
        db_session, tower_id=tower.id, recorded_by=member.id, category="cleaning",
        amount=Decimal("1500.00"), expenditure_date=date(2026, 7, 5),
    )
    await make_expenditure(
        db_session, tower_id=tower.id, recorded_by=member.id, category="cleaning",
        amount=Decimal("500.00"), expenditure_date=date(2026, 7, 10),
    )
    await make_expenditure(
        db_session, tower_id=tower.id, recorded_by=member.id, category="repairs",
        amount=Decimal("3000.00"), expenditure_date=date(2026, 7, 15),
    )
    # Out of period — must not be included.
    await make_expenditure(
        db_session, tower_id=tower.id, recorded_by=member.id, category="repairs",
        amount=Decimal("9999.00"), expenditure_date=date(2026, 8, 1),
    )
    await db_session.commit()

    await _login(client, user.email)
    resp = await client.get(
        f"/api/v1/towers/{tower.id}/reports/expenditure",
        params={"period_start": "2026-07-01", "period_end": "2026-07-31"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 3
    totals = {c["category"]: Decimal(c["total"]) for c in body["category_totals"]}
    assert totals["cleaning"] == Decimal("2000.00")
    assert totals["repairs"] == Decimal("3000.00")
    assert Decimal(body["grand_total"]) == Decimal("5000.00")


@pytest.mark.asyncio
async def test_expenditure_report_excludes_deactivated_expenditures(client, db_session):
    tower, user, member = await _setup_reports_admin(db_session)
    expenditure = await make_expenditure(
        db_session, tower_id=tower.id, recorded_by=member.id, amount=Decimal("100.00"),
        expenditure_date=date(2026, 7, 5),
    )
    from datetime import UTC, datetime

    expenditure.deactivated_at = datetime.now(UTC)
    await db_session.commit()

    await _login(client, user.email)
    resp = await client.get(
        f"/api/v1/towers/{tower.id}/reports/expenditure",
        params={"period_start": "2026-07-01", "period_end": "2026-07-31"},
    )
    body = resp.json()
    assert body["items"] == []
    assert Decimal(body["grand_total"]) == Decimal("0.00")


@pytest.mark.asyncio
async def test_expenditure_report_zero_expenditures_is_200_not_error(client, db_session):
    tower, user, _member = await _setup_reports_admin(db_session)
    await db_session.commit()
    await _login(client, user.email)
    resp = await client.get(
        f"/api/v1/towers/{tower.id}/reports/expenditure",
        params={"period_start": "2026-01-01", "period_end": "2026-01-31"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["category_totals"] == []
    assert Decimal(body["grand_total"]) == Decimal("0.00")
