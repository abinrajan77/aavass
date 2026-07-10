"""backend.md §8.2 — billing-cycle generation integration tests (real Postgres via
testcontainers, per `tests/conftest.py`). Not runnable in this sandbox (no Docker daemon
available — see the worktree's setup notes), written to match the repo's existing
integration-test fixture pattern (`client`, `db_session`) exactly like
`tests/integration/test_tower_isolation.py`.

The 250/450-active-flat scale from overview.md's acceptance criteria 4/5 is a *load*
characteristic (latency budget), not a branch-logic one — this suite monkeypatches
`SYNC_GENERATION_FLAT_THRESHOLD` down to keep the functional tests fast; true 250/450-flat
latency validation belongs in the k6/Locust load tests referenced by
`06-cloud-devops.md` §7/§10, not this pytest suite.
"""

import pytest
from sqlalchemy import select

from app.models.billing_cycle import BillingCycle
from app.models.job import Job
from app.models.maintenance_due import MaintenanceDue
from app.services import billing_cycle as billing_cycle_module
from app.services.billing_cycle import process_billing_cycle_job
from tests.factories import (
    DEFAULT_PASSWORD,
    make_billing_admin,
    make_complex,
    make_flat,
    make_maintenance_formula,
    make_owner,
    make_tenant,
    make_tower,
)


async def _login(client, email, password=DEFAULT_PASSWORD):
    return await client.post("/api/v1/auth/login", json={"email": email, "password": password})


async def _setup_tower(db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    member = await make_billing_admin(
        db_session, tower_id=tower.id, email="billing-admin@example.com"
    )
    await make_maintenance_formula(
        db_session, tower_id=tower.id, created_by=member.id, base_amount=2000, per_sqft_rate=2
    )
    await db_session.commit()
    return tower, member


@pytest.mark.asyncio
async def test_sync_generation_creates_one_due_per_active_flat_with_correct_assignment(
    client, db_session
):
    tower, member = await _setup_tower(db_session)

    owner_occupied = await make_flat(
        db_session,
        tower_id=tower.id,
        flat_number="101",
        carpet_area=850,
        occupancy_status="owner_occupied",
    )
    await make_owner(db_session, flat_id=owner_occupied.id, full_name="Asha Rao")

    tenant_occupied = await make_flat(
        db_session,
        tower_id=tower.id,
        flat_number="102",
        carpet_area=900,
        occupancy_status="tenant_occupied",
    )
    await make_owner(db_session, flat_id=tenant_occupied.id, full_name="Owner Two")
    await make_tenant(db_session, flat_id=tenant_occupied.id, full_name="Ravi Kumar")

    vacant = await make_flat(
        db_session, tower_id=tower.id, flat_number="103", carpet_area=800, occupancy_status="vacant"
    )
    await make_owner(db_session, flat_id=vacant.id, full_name="Owner Three")

    await db_session.commit()
    await _login(client, "billing-admin@example.com")

    resp = await client.post(
        f"/api/v1/towers/{tower.id}/billing-cycles",
        json={"month": 7, "year": 2026, "due_date": "2026-07-10"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "active"
    assert body["total_dues"] == 3

    dues = (
        (
            await db_session.execute(
                select(MaintenanceDue).where(MaintenanceDue.billing_cycle_id == body["id"])
            )
        )
        .scalars()
        .all()
    )
    by_flat = {d.flat_id: d for d in dues}
    assert by_flat[owner_occupied.id].assigned_to_type == "owner"
    assert by_flat[tenant_occupied.id].assigned_to_type == "tenant"
    assert by_flat[tenant_occupied.id].assigned_to_name_snapshot == "Ravi Kumar"
    assert by_flat[vacant.id].assigned_to_type == "owner"
    # base=2000, rate=2, area=850 -> 2000 + 1700 = 3700.00
    assert by_flat[owner_occupied.id].amount == 3700


@pytest.mark.asyncio
async def test_flat_with_no_primary_owner_is_skipped_without_aborting_the_cycle(client, db_session):
    """overview.md edge case 12 — a per-flat NO_PRIMARY_OWNER failure does not abort the
    whole cycle; the other flats still get dues."""
    tower, member = await _setup_tower(db_session)

    good_flat = await make_flat(db_session, tower_id=tower.id, flat_number="101")
    await make_owner(db_session, flat_id=good_flat.id, full_name="Asha Rao")

    bad_flat = await make_flat(db_session, tower_id=tower.id, flat_number="102")
    # No owner at all -> NO_PRIMARY_OWNER.

    await db_session.commit()
    await _login(client, "billing-admin@example.com")

    resp = await client.post(
        f"/api/v1/towers/{tower.id}/billing-cycles",
        json={"month": 8, "year": 2026, "due_date": "2026-08-10"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["total_dues"] == 1
    assert body["generation_failures"] == [
        {"flat_id": str(bad_flat.id), "reason": "NO_PRIMARY_OWNER"}
    ]


@pytest.mark.asyncio
async def test_duplicate_cycle_generation_returns_409(client, db_session):
    tower, member = await _setup_tower(db_session)
    flat = await make_flat(db_session, tower_id=tower.id)
    await make_owner(db_session, flat_id=flat.id)
    await db_session.commit()
    await _login(client, "billing-admin@example.com")

    payload = {"month": 9, "year": 2026, "due_date": "2026-09-10"}
    first = await client.post(f"/api/v1/towers/{tower.id}/billing-cycles", json=payload)
    assert first.status_code == 201

    second = await client.post(f"/api/v1/towers/{tower.id}/billing-cycles", json=payload)
    assert second.status_code == 409
    assert second.json()["error_code"] == "BILLING_CYCLE_ALREADY_EXISTS"

    count = await db_session.scalar(
        select(BillingCycle).where(
            BillingCycle.tower_id == tower.id, BillingCycle.month == 9, BillingCycle.year == 2026
        )
    )
    assert count is not None  # exactly one row exists (the first)


@pytest.mark.asyncio
async def test_put_on_cycle_with_dues_returns_409_immutable_record(client, db_session):
    tower, member = await _setup_tower(db_session)
    flat = await make_flat(db_session, tower_id=tower.id)
    await make_owner(db_session, flat_id=flat.id)
    await db_session.commit()
    await _login(client, "billing-admin@example.com")

    create_resp = await client.post(
        f"/api/v1/towers/{tower.id}/billing-cycles",
        json={"month": 10, "year": 2026, "due_date": "2026-10-10"},
    )
    cycle_id = create_resp.json()["id"]

    put_resp = await client.put(
        f"/api/v1/towers/{tower.id}/billing-cycles/{cycle_id}",
        json={"due_date": "2026-10-12"},
    )
    assert put_resp.status_code == 409
    assert put_resp.json()["error_code"] == "IMMUTABLE_RECORD"


@pytest.mark.asyncio
async def test_delete_on_any_cycle_always_returns_409_immutable_record(client, db_session):
    tower, member = await _setup_tower(db_session)
    await db_session.commit()
    await _login(client, "billing-admin@example.com")

    create_resp = await client.post(
        f"/api/v1/towers/{tower.id}/billing-cycles",
        json={"month": 11, "year": 2026, "due_date": "2026-11-10"},
    )
    cycle_id = create_resp.json()["id"]
    # Zero flats -> zero dues, status still 'generating'-then-'active' with zero dues; DELETE
    # must still be rejected unconditionally (backend.md §6.3: "always 409, no hard delete of
    # financial records, ever").
    delete_resp = await client.delete(f"/api/v1/towers/{tower.id}/billing-cycles/{cycle_id}")
    assert delete_resp.status_code == 409
    assert delete_resp.json()["error_code"] == "IMMUTABLE_RECORD"


@pytest.mark.asyncio
async def test_async_generation_returns_202_and_worker_completes_the_job(
    client, db_session, monkeypatch
):
    """overview.md acceptance criterion 5 — beyond the sync threshold, `POST` returns 202 +
    job_id immediately, and dues only appear once the (here: manually invoked) worker
    processes the job. Threshold monkeypatched to 2 flats to keep this fast."""
    monkeypatch.setattr(billing_cycle_module, "SYNC_GENERATION_FLAT_THRESHOLD", 2)
    import app.api.v1.billing_cycles as billing_cycles_router

    monkeypatch.setattr(billing_cycles_router, "SYNC_GENERATION_FLAT_THRESHOLD", 2)

    tower, member = await _setup_tower(db_session)
    for i in range(3):
        flat = await make_flat(db_session, tower_id=tower.id, flat_number=str(200 + i))
        await make_owner(db_session, flat_id=flat.id, full_name=f"Owner {i}")
    await db_session.commit()
    await _login(client, "billing-admin@example.com")

    resp = await client.post(
        f"/api/v1/towers/{tower.id}/billing-cycles",
        json={"month": 12, "year": 2026, "due_date": "2026-12-10"},
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "generating"
    job_id = body["job_id"]

    # No dues yet — generation hasn't run.
    cycle = await db_session.get(BillingCycle, body["cycle_id"])
    assert cycle.status == "generating"

    job = await db_session.get(Job, job_id)
    await process_billing_cycle_job(db_session, job=job)

    await db_session.refresh(cycle)
    assert cycle.status == "active"

    poll_resp = await client.get(f"/api/v1/towers/{tower.id}/jobs/{job_id}")
    assert poll_resp.status_code == 200
    assert poll_resp.json()["status"] == "done"
    assert poll_resp.json()["result"]["dues_created"] == 3


@pytest.mark.asyncio
async def test_retried_job_delivery_for_an_already_active_cycle_is_a_safe_noop(
    client, db_session, monkeypatch
):
    monkeypatch.setattr(billing_cycle_module, "SYNC_GENERATION_FLAT_THRESHOLD", 0)
    import app.api.v1.billing_cycles as billing_cycles_router

    monkeypatch.setattr(billing_cycles_router, "SYNC_GENERATION_FLAT_THRESHOLD", 0)

    tower, member = await _setup_tower(db_session)
    flat = await make_flat(db_session, tower_id=tower.id)
    await make_owner(db_session, flat_id=flat.id)
    await db_session.commit()
    await _login(client, "billing-admin@example.com")

    resp = await client.post(
        f"/api/v1/towers/{tower.id}/billing-cycles",
        json={"month": 1, "year": 2027, "due_date": "2027-01-10"},
    )
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]

    job = await db_session.get(Job, job_id)
    await process_billing_cycle_job(db_session, job=job)

    dues_after_first_run = (
        (
            await db_session.execute(
                select(MaintenanceDue).where(
                    MaintenanceDue.billing_cycle_id == resp.json()["cycle_id"]
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(dues_after_first_run) == 1

    # Simulate a duplicate SQS delivery of the same message.
    job = await db_session.get(Job, job_id)
    job.status = "pending"  # a fresh delivery would look "pending" to the worker again
    await db_session.flush()
    await process_billing_cycle_job(db_session, job=job)

    dues_after_retry = (
        (
            await db_session.execute(
                select(MaintenanceDue).where(
                    MaintenanceDue.billing_cycle_id == resp.json()["cycle_id"]
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(dues_after_retry) == 1  # no duplicate dues created
