"""Export flow — backend.md §2.6, overview.md acceptance criterion 6, backend test plan's
row-count threshold + idempotency checks. The >5000-row branch is exercised by monkeypatching
`app.services.export.estimate_row_count` (constructing 5001 real rows in a test DB would be
needlessly slow) rather than the row-count check itself — the router's *branching logic* is
what's under test, and it dispatches purely on that function's return value."""

from uuid import UUID, uuid4

import pytest

from app.models.export_job import ExportJob
from app.models.job import Job
from app.services import export as export_service
from tests.factories import (
    DEFAULT_PASSWORD,
    make_association_member,
    make_complex,
    make_role,
    make_tenant,
    make_tower,
    make_user,
)
from tests.factories import make_flat as _make_flat


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
async def test_export_csv_sync_for_small_row_count(client, db_session):
    tower, user, _member = await _setup_reports_admin(db_session)
    flat = await _make_flat(db_session, tower_id=tower.id, flat_number="701")
    await make_tenant(db_session, flat_id=flat.id, full_name="Sync Export Tenant")
    await db_session.commit()

    await _login(client, user.email)
    resp = await client.get(
        f"/api/v1/towers/{tower.id}/reports/tenant-register", params={"format": "csv"}
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "attachment" in resp.headers["content-disposition"]
    assert "Sync Export Tenant" in resp.text
    assert "tenant_name" in resp.text  # CSV header row


@pytest.mark.asyncio
async def test_export_pdf_sync_for_small_row_count(client, db_session):
    tower, user, _member = await _setup_reports_admin(db_session)
    flat = await _make_flat(db_session, tower_id=tower.id, flat_number="702")
    await make_tenant(db_session, flat_id=flat.id, full_name="PDF Export Tenant")
    await db_session.commit()

    await _login(client, user.email)
    resp = await client.get(
        f"/api/v1/towers/{tower.id}/reports/tenant-register", params={"format": "pdf"}
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF-1.4")
    assert b"PDF Export Tenant" in resp.content


@pytest.mark.asyncio
async def test_export_over_threshold_enqueues_job_and_returns_202(client, db_session, monkeypatch):
    tower, user, _member = await _setup_reports_admin(db_session)
    await db_session.commit()

    async def _fake_estimate(db, *, tower_id, report_type, params):
        return export_service.SYNC_EXPORT_ROW_THRESHOLD + 1

    monkeypatch.setattr(export_service, "estimate_row_count", _fake_estimate)

    await _login(client, user.email)
    resp = await client.get(
        f"/api/v1/towers/{tower.id}/reports/tenant-register", params={"format": "csv"}
    )
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]
    assert job_id

    export_job = await db_session.get(ExportJob, UUID(job_id))
    assert export_job is not None
    assert export_job.status == "pending"
    assert export_job.tower_id == tower.id
    assert export_job.report_type == "tenant_register"
    assert export_job.format == "csv"

    job = await db_session.get(Job, UUID(job_id))
    assert job is not None
    assert job.job_type == "report_export"
    assert job.status == "pending"


@pytest.mark.asyncio
async def test_duplicate_export_request_is_idempotent(client, db_session, monkeypatch):
    """backend test plan: a duplicate/retried export request with an identical
    (tower_id, report_type, format, params) natural key while a prior job is still
    pending/running does not enqueue a second job — same job_id returned both times."""
    tower, user, _member = await _setup_reports_admin(db_session)
    await db_session.commit()

    async def _fake_estimate(db, *, tower_id, report_type, params):
        return export_service.SYNC_EXPORT_ROW_THRESHOLD + 1

    monkeypatch.setattr(export_service, "estimate_row_count", _fake_estimate)

    await _login(client, user.email)
    resp1 = await client.get(
        f"/api/v1/towers/{tower.id}/reports/tenant-register", params={"format": "csv"}
    )
    resp2 = await client.get(
        f"/api/v1/towers/{tower.id}/reports/tenant-register", params={"format": "csv"}
    )
    assert resp1.status_code == 202
    assert resp2.status_code == 202
    assert resp1.json()["job_id"] == resp2.json()["job_id"]

    from sqlalchemy import func, select

    count = await db_session.scalar(
        select(func.count()).select_from(ExportJob).where(ExportJob.tower_id == tower.id)
    )
    assert count == 1


@pytest.mark.asyncio
async def test_report_export_job_processing_sets_download_url_on_shared_jobs_route(
    client, db_session, monkeypatch
):
    """The frontend must be able to poll the ONE shared `/jobs/{job_id}` route and see
    `result.download_url` once done — this exercises the worker-equivalent function directly
    (no real SQS consumer in this sandbox), mirroring
    `app.services.billing_cycle.process_billing_cycle_job`'s own test pattern."""
    tower, user, _member = await _setup_reports_admin(db_session)
    flat = await _make_flat(db_session, tower_id=tower.id, flat_number="703")
    await make_tenant(db_session, flat_id=flat.id, full_name="Async Export Tenant")
    await db_session.commit()

    async def _fake_estimate(db, *, tower_id, report_type, params):
        return export_service.SYNC_EXPORT_ROW_THRESHOLD + 1

    monkeypatch.setattr(export_service, "estimate_row_count", _fake_estimate)

    await _login(client, user.email)
    resp = await client.get(
        f"/api/v1/towers/{tower.id}/reports/tenant-register", params={"format": "csv"}
    )
    job_id = resp.json()["job_id"]

    job = await db_session.get(Job, UUID(job_id))
    assert job is not None
    await export_service.process_report_export_job(db_session, job=job)

    poll_resp = await client.get(f"/api/v1/towers/{tower.id}/jobs/{job_id}")
    assert poll_resp.status_code == 200
    poll_body = poll_resp.json()
    assert poll_body["status"] == "done"
    assert poll_body["result"]["download_url"]

    export_job = await db_session.get(ExportJob, UUID(job_id))
    assert export_job is not None
    assert export_job.status == "done"
    assert export_job.file_s3_key is not None
