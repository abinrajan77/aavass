"""Collection vs Expenditure Summary — backend.md §2.4, overview.md acceptance criterion 4,
backend test plan reconciliation checks (no double-counting across maintenance/special-
collection payment sources)."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from app.models.payment import Payment
from app.services.payments import record_payment
from tests.factories import (
    DEFAULT_PASSWORD,
    make_association_member,
    make_billing_cycle,
    make_complex,
    make_expenditure,
    make_flat,
    make_maintenance_due,
    make_maintenance_formula,
    make_primary_owner_for_flat,
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
async def test_collection_vs_expenditure_reconciles_no_double_counting(client, db_session):
    from app.models.special_collection_due import SpecialCollectionDue
    from tests.factories import make_special_collection

    tower, user, member = await _setup_reports_admin(db_session)
    formula = await make_maintenance_formula(db_session, tower_id=tower.id, created_by=member.id)
    cycle = await make_billing_cycle(
        db_session, tower_id=tower.id, formula_id=formula.id, created_by=member.id,
        month=7, year=2026,
    )
    flat = await make_flat(db_session, tower_id=tower.id, flat_number="601")
    owner = await make_primary_owner_for_flat(
        db_session, flat_id=flat.id, created_by_user_id=user.id
    )
    due = await make_maintenance_due(
        db_session, billing_cycle_id=cycle.id, tower_id=tower.id, flat_id=flat.id,
        primary_owner_id=owner.id, amount=Decimal("2000.00"),
    )

    collection = await make_special_collection(db_session, tower_id=tower.id, created_by=member.id)
    sc_due = SpecialCollectionDue(
        special_collection_id=collection.id, tower_id=tower.id, flat_id=flat.id,
        flat_number=flat.flat_number, owner_id=owner.id, owner_name=owner.full_name,
        amount=Decimal("500.00"), due_date=date(2026, 7, 15), status="pending",
    )
    db_session.add(sc_due)
    await db_session.flush()

    await make_expenditure(
        db_session, tower_id=tower.id, recorded_by=member.id, category="utilities",
        amount=Decimal("700.00"), expenditure_date=date(2026, 7, 20),
    )
    await db_session.commit()

    await record_payment(
        db_session, tower_id=tower.id, due_type="maintenance", due_id=due.id,
        payment_date=date(2026, 7, 10), amount_received=Decimal("2000.00"), payment_mode="cash",
        reference_number=None, recorded_by=member,
    )
    # `record_payment()`'s "special_collection" dispatch-table entries are never actually
    # registered anywhere in this codebase (see `app/services/payments.py`'s module docstring
    # claim vs. reality — confirmed by grepping for `register_due_resolver` call sites and by
    # `tests/integration/test_special_collections.py`'s own "Module 3's mark-paid endpoint is
    # out of scope for this slice" comment). This report's own code never calls
    # `record_payment` — it queries `payments` directly — so insert the `Payment` row at the
    # DB layer directly here, exactly like that existing test does for `due.status`.
    sc_due.status = "paid"
    db_session.add(
        Payment(
            tower_id=tower.id, due_type="special_collection", due_id=sc_due.id,
            payment_date=date(2026, 7, 12), amount_received=Decimal("500.00"),
            payment_mode="cash", recorded_by=member.id,
        )
    )
    await db_session.commit()

    await _login(client, user.email)
    resp = await client.get(
        f"/api/v1/towers/{tower.id}/reports/collection-vs-expenditure",
        params={"period_type": "month", "month": 7, "year": 2026},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert Decimal(body["maintenance_collected"]) == Decimal("2000.00")
    assert Decimal(body["special_collection_collected"]) == Decimal("500.00")
    assert Decimal(body["total_collected"]) == Decimal("2500.00")
    assert Decimal(body["total_expenditure"]) == Decimal("700.00")
    assert Decimal(body["net"]) == Decimal("1800.00")
    assert body["period_label"] == "July 2026"


@pytest.mark.asyncio
async def test_collection_vs_expenditure_zero_expenditures_returns_200(client, db_session):
    tower, user, _member = await _setup_reports_admin(db_session)
    await db_session.commit()
    await _login(client, user.email)
    resp = await client.get(
        f"/api/v1/towers/{tower.id}/reports/collection-vs-expenditure",
        params={"period_type": "month", "month": 1, "year": 2026},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert Decimal(body["total_expenditure"]) == Decimal("0.00")
    assert body["expenditure_by_category"] == []


@pytest.mark.asyncio
async def test_collection_vs_expenditure_financial_year_period(client, db_session):
    tower, user, member = await _setup_reports_admin(db_session)
    await make_expenditure(
        db_session, tower_id=tower.id, recorded_by=member.id, amount=Decimal("100.00"),
        expenditure_date=date(2025, 4, 1),
    )
    await make_expenditure(
        db_session, tower_id=tower.id, recorded_by=member.id, amount=Decimal("200.00"),
        expenditure_date=date(2026, 3, 31),
    )
    # Out of FY 2025-26 (before Apr 1, 2025).
    await make_expenditure(
        db_session, tower_id=tower.id, recorded_by=member.id, amount=Decimal("999.00"),
        expenditure_date=date(2025, 3, 31),
    )
    await db_session.commit()

    await _login(client, user.email)
    resp = await client.get(
        f"/api/v1/towers/{tower.id}/reports/collection-vs-expenditure",
        params={"period_type": "financial_year", "year": 2025},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["period_label"] == "FY 2025-26"
    assert Decimal(body["total_expenditure"]) == Decimal("300.00")
