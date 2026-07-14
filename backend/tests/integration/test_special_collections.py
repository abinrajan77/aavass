"""Integration tests for the special-collections slice — backend.md test plan items 1-5, plus
mark-paid (item 6, see `test_mark_special_collection_due_paid_*` below).

Module 2 (Flat/Owner/Tenant) doesn't exist in this codebase yet, so every test here
overrides `app.services.flat_directory.get_flat_directory` with a `FakeFlatDirectory`
seeded via `make_active_flat_record` (see `tests/factories.py`) — the same
`app.dependency_overrides` pattern `tests/conftest.py` already uses for `get_db`. This
exercises the real HTTP endpoint, the real equal-split algorithm, and real DB writes; only
the Module-2 data source is swapped.

Mark-paid delegates to Module 3's shared `record_payment(due_type="special_collection", ...)`
— `app/services/special_collection.py` registers the due/label/owner-name resolvers that
dispatch needs at import time.
"""

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.main import app
from app.models.special_collection_due import SpecialCollectionDue
from app.services.flat_directory import get_flat_directory
from tests.factories import (
    DEFAULT_PASSWORD,
    FakeFlatDirectory,
    make_active_flat_record,
    make_association_member,
    make_complex,
    make_role,
    make_tower,
    make_user,
)


async def _login(client, email, password=DEFAULT_PASSWORD):
    return await client.post("/api/v1/auth/login", json={"email": email, "password": password})


async def _setup_tower_with_admin(db_session, *, permission_codes):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    role = await make_role(db_session, tower_id=tower.id, permission_codes=permission_codes)
    user = await make_user(db_session, email=f"admin-{uuid4()}@example.com")
    await make_association_member(db_session, tower_id=tower.id, user_id=user.id, role_id=role.id)
    await db_session.commit()
    return tower, user


def _override_flat_directory(fake_directory: FakeFlatDirectory):
    app.dependency_overrides[get_flat_directory] = lambda: fake_directory


def _clear_flat_directory_override():
    app.dependency_overrides.pop(get_flat_directory, None)


@pytest.mark.asyncio
async def test_due_generation_targets_owner_not_tenant(client, db_session):
    tower, user = await _setup_tower_with_admin(
        db_session, permission_codes=["MANAGE_SPECIAL_COLLECTIONS", "VIEW_TOWER_DATA"]
    )
    owner_id = uuid4()
    tenant_id = uuid4()  # never referenced anywhere in the fixture's flat record
    flat_record = make_active_flat_record(
        flat_number="101", owner_id=owner_id, owner_name="Jane Owner"
    )
    _override_flat_directory(FakeFlatDirectory({tower.id: [flat_record]}))
    try:
        await _login(client, user.email)
        resp = await client.post(
            f"/api/v1/towers/{tower.id}/special-collections",
            json={
                "title": "Tenant-occupied flat test",
                "total_amount": "1000.00",
                "due_date": "2026-09-01",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["dues_generated"] is True

        dues_resp = await client.get(
            f"/api/v1/towers/{tower.id}/special-collections/{body['id']}/dues"
        )
        assert dues_resp.status_code == 200
        items = dues_resp.json()["items"]
        assert len(items) == 1
        assert items[0]["owner_id"] == str(owner_id)
        assert items[0]["owner_id"] != str(tenant_id)
        assert items[0]["flat_id"] == str(flat_record.flat_id)
    finally:
        _clear_flat_directory_override()


@pytest.mark.asyncio
async def test_equal_split_calculation_with_correct_rounding(client, db_session):
    tower, user = await _setup_tower_with_admin(
        db_session, permission_codes=["MANAGE_SPECIAL_COLLECTIONS", "VIEW_TOWER_DATA"]
    )
    flats = [make_active_flat_record(flat_number=str(100 + i)) for i in range(7)]
    _override_flat_directory(FakeFlatDirectory({tower.id: flats}))
    try:
        await _login(client, user.email)
        resp = await client.post(
            f"/api/v1/towers/{tower.id}/special-collections",
            json={
                "title": "Equal split test",
                "total_amount": "100000.00",
                "due_date": "2026-09-01",
            },
        )
        assert resp.status_code == 201
        collection_id = resp.json()["id"]

        dues_resp = await client.get(
            f"/api/v1/towers/{tower.id}/special-collections/{collection_id}/dues",
            params={"page_size": 25},
        )
        items = dues_resp.json()["items"]
        assert len(items) == 7

        total_paise = 100000 * 100
        base_paise, remainder = divmod(total_paise, 7)
        assert remainder == 3

        amounts_sum = sum(Decimal(item["amount"]) for item in items)
        assert amounts_sum == Decimal("100000.00")

        base_amount = Decimal(base_paise) / 100
        ordered = sorted(items, key=lambda i: int(i["flat_number"]))
        extra_flats = [i["flat_number"] for i in ordered if Decimal(i["amount"]) > base_amount]
        assert len(extra_flats) == remainder
        assert extra_flats == [f["flat_number"] for f in ordered[:remainder]]
    finally:
        _clear_flat_directory_override()


@pytest.mark.asyncio
async def test_flat_with_no_active_owner_is_skipped_not_fatal(client, db_session):
    tower, user = await _setup_tower_with_admin(
        db_session, permission_codes=["MANAGE_SPECIAL_COLLECTIONS", "VIEW_TOWER_DATA"]
    )
    flats = [make_active_flat_record(flat_number=str(100 + i)) for i in range(9)]
    flats.append(make_active_flat_record(flat_number="110", no_active_owner=True))
    _override_flat_directory(FakeFlatDirectory({tower.id: flats}))
    try:
        await _login(client, user.email)
        resp = await client.post(
            f"/api/v1/towers/{tower.id}/special-collections",
            json={
                "title": "Skip test",
                "total_amount": "90000.00",
                "due_date": "2026-09-01",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert len(body["skipped_flats"]) == 1
        assert body["skipped_flats"][0]["flat_number"] == "110"
        assert body["skipped_flats"][0]["reason"] == "NO_ACTIVE_OWNER"

        dues_resp = await client.get(
            f"/api/v1/towers/{tower.id}/special-collections/{body['id']}/dues",
            params={"page_size": 25},
        )
        assert dues_resp.json()["total"] == 9
        assert all(i["flat_number"] != "110" for i in dues_resp.json()["items"])
    finally:
        _clear_flat_directory_override()


@pytest.mark.asyncio
async def test_multiple_simultaneous_open_special_collections(client, db_session):
    tower, user = await _setup_tower_with_admin(
        db_session, permission_codes=["MANAGE_SPECIAL_COLLECTIONS", "VIEW_TOWER_DATA"]
    )
    flats = [make_active_flat_record(flat_number=str(100 + i)) for i in range(3)]
    _override_flat_directory(FakeFlatDirectory({tower.id: flats}))
    try:
        await _login(client, user.email)
        resp_a = await client.post(
            f"/api/v1/towers/{tower.id}/special-collections",
            json={"title": "Collection A", "total_amount": "3000.00", "due_date": "2026-09-01"},
        )
        assert resp_a.status_code == 201
        resp_b = await client.post(
            f"/api/v1/towers/{tower.id}/special-collections",
            json={"title": "Collection B", "total_amount": "6000.00", "due_date": "2026-10-01"},
        )
        assert resp_b.status_code == 201

        collection_a_id = resp_a.json()["id"]
        collection_b_id = resp_b.json()["id"]
        assert collection_a_id != collection_b_id

        dues_a_url = f"/api/v1/towers/{tower.id}/special-collections/{collection_a_id}/dues"
        dues_b_url = f"/api/v1/towers/{tower.id}/special-collections/{collection_b_id}/dues"
        dues_a = (await client.get(dues_a_url)).json()["items"]
        dues_b = (await client.get(dues_b_url)).json()["items"]

        assert len(dues_a) == 3
        assert len(dues_b) == 3
        ids_a = {d["id"] for d in dues_a}
        ids_b = {d["id"] for d in dues_b}
        assert ids_a.isdisjoint(ids_b)
    finally:
        _clear_flat_directory_override()


@pytest.mark.asyncio
async def test_special_collection_immutable_no_put_route(client, db_session):
    tower, user = await _setup_tower_with_admin(
        db_session, permission_codes=["MANAGE_SPECIAL_COLLECTIONS", "VIEW_TOWER_DATA"]
    )
    _override_flat_directory(FakeFlatDirectory({tower.id: []}))
    try:
        await _login(client, user.email)
        resp = await client.post(
            f"/api/v1/towers/{tower.id}/special-collections",
            json={"title": "Immutability test", "total_amount": "500.00", "due_date": "2026-09-01"},
        )
        assert resp.status_code == 201
        collection_id = resp.json()["id"]

        put_resp = await client.put(
            f"/api/v1/towers/{tower.id}/special-collections/{collection_id}",
            json={"title": "Should not be allowed"},
        )
        assert put_resp.status_code == 405
    finally:
        _clear_flat_directory_override()


@pytest.mark.asyncio
async def test_special_collection_cannot_cancel_once_a_due_is_paid(client, db_session):
    tower, user = await _setup_tower_with_admin(
        db_session, permission_codes=["MANAGE_SPECIAL_COLLECTIONS", "VIEW_TOWER_DATA"]
    )
    flats = [make_active_flat_record(flat_number="101")]
    _override_flat_directory(FakeFlatDirectory({tower.id: flats}))
    try:
        await _login(client, user.email)
        resp = await client.post(
            f"/api/v1/towers/{tower.id}/special-collections",
            json={"title": "Cancel test", "total_amount": "1000.00", "due_date": "2026-09-01"},
        )
        assert resp.status_code == 201
        collection_id = resp.json()["id"]

        # Module 3's mark-paid endpoint is out of scope for this slice — simulate the paid
        # state directly at the DB layer, which is all this test needs to exercise the
        # cancel-immutability guard.
        due = await db_session.scalar(
            select(SpecialCollectionDue).where(
                SpecialCollectionDue.special_collection_id == collection_id
            )
        )
        due.status = "paid"
        await db_session.commit()

        delete_resp = await client.delete(
            f"/api/v1/towers/{tower.id}/special-collections/{collection_id}"
        )
        assert delete_resp.status_code == 409
        assert delete_resp.json()["error_code"] == "IMMUTABLE_RECORD"
    finally:
        _clear_flat_directory_override()


@pytest.mark.asyncio
async def test_special_collection_can_cancel_when_no_dues_paid(client, db_session):
    tower, user = await _setup_tower_with_admin(
        db_session, permission_codes=["MANAGE_SPECIAL_COLLECTIONS", "VIEW_TOWER_DATA"]
    )
    flats = [make_active_flat_record(flat_number="101")]
    _override_flat_directory(FakeFlatDirectory({tower.id: flats}))
    try:
        await _login(client, user.email)
        resp = await client.post(
            f"/api/v1/towers/{tower.id}/special-collections",
            json={"title": "Cancel-ok test", "total_amount": "1000.00", "due_date": "2026-09-01"},
        )
        collection_id = resp.json()["id"]

        delete_resp = await client.delete(
            f"/api/v1/towers/{tower.id}/special-collections/{collection_id}"
        )
        assert delete_resp.status_code == 200
        assert delete_resp.json()["id"] == collection_id
    finally:
        _clear_flat_directory_override()


@pytest.mark.asyncio
async def test_mark_special_collection_due_paid_creates_receipt_and_flips_status(
    client, db_session
):
    tower, user = await _setup_tower_with_admin(
        db_session,
        permission_codes=["MANAGE_SPECIAL_COLLECTIONS", "VIEW_TOWER_DATA", "RECORD_PAYMENT"],
    )
    flats = [make_active_flat_record(flat_number="101", owner_name="Asha Rao")]
    _override_flat_directory(FakeFlatDirectory({tower.id: flats}))
    try:
        await _login(client, user.email)
        create_resp = await client.post(
            f"/api/v1/towers/{tower.id}/special-collections",
            json={
                "title": "Lift Modernization Fund",
                "total_amount": "1000.00",
                "due_date": "2026-09-01",
            },
        )
        collection_id = create_resp.json()["id"]
        due_id = (
            await client.get(f"/api/v1/towers/{tower.id}/special-collections/{collection_id}/dues")
        ).json()["items"][0]["id"]

        resp = await client.patch(
            f"/api/v1/towers/{tower.id}/special-collections/{collection_id}/dues/{due_id}/mark-paid",
            json={
                "payment_date": "2026-09-05",
                "amount_received": "1000.00",
                "payment_mode": "cash",
                "reference_number": None,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["due"]["status"] == "paid"
        assert body["receipt"]["receipt_number"]
        assert body["receipt"]["owner_name_snapshot"] == "Asha Rao"
        assert (
            body["receipt"]["billing_period_label"]
            == "Special Collection: Lift Modernization Fund"
        )
        assert body["receipt"]["download_url"]

        # A second mark-paid on the same due must not double-pay.
        second = await client.patch(
            f"/api/v1/towers/{tower.id}/special-collections/{collection_id}/dues/{due_id}/mark-paid",
            json={
                "payment_date": "2026-09-06",
                "amount_received": "1000.00",
                "payment_mode": "cash",
                "reference_number": None,
            },
        )
        assert second.status_code == 409
        assert second.json()["error_code"] == "DUE_ALREADY_PAID"
    finally:
        _clear_flat_directory_override()
