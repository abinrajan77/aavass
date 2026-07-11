"""Integration tests for the expenditures slice — backend.md test plan items 9-12.

Uses moto's `mock_aws()` to fake S3 for the attachment upload/download round-trip
(backend.md test plan item 9 explicitly calls out "mocked S3 in CI, e.g. via moto") —
the presigned PUT/GET URLs are exercised with real HTTP calls (`requests`), not just
inspected as strings, since moto intercepts matching AWS-hostname traffic regardless of
which client issued it.
"""

from decimal import Decimal
from uuid import uuid4

import boto3
import pytest
import requests
from moto import mock_aws

from app.core.config import get_settings
from tests.factories import (
    DEFAULT_PASSWORD,
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


def _fake_aws_creds(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "ap-south-1")


@pytest.mark.asyncio
async def test_expenditure_attachment_upload_and_download_round_trip(
    client, db_session, monkeypatch
):
    _fake_aws_creds(monkeypatch)
    tower, user = await _setup_tower_with_admin(
        db_session, permission_codes=["MANAGE_EXPENDITURE", "VIEW_TOWER_DATA"]
    )
    await _login(client, user.email)

    with mock_aws():
        settings = get_settings()
        boto3.client("s3", region_name=settings.aws_region).create_bucket(
            Bucket=settings.s3_bucket_name,
            CreateBucketConfiguration={"LocationConstraint": settings.aws_region},
        )

        upload_resp = await client.post(
            f"/api/v1/towers/{tower.id}/expenditures/attachment-upload-url",
            json={"filename": "invoice.pdf", "content_type": "application/pdf"},
        )
        assert upload_resp.status_code == 201
        upload_body = upload_resp.json()
        assert upload_body["attachment_s3_key"].startswith(
            f"expenditure-attachments/{tower.id}/"
        )
        assert upload_body["attachment_s3_key"].endswith("/invoice.pdf")

        put_resp = requests.put(
            upload_body["upload_url"],
            data=b"%PDF-1.4 fake pdf bytes",
            headers={"Content-Type": "application/pdf"},
            timeout=10,
        )
        assert put_resp.status_code == 200

        create_resp = await client.post(
            f"/api/v1/towers/{tower.id}/expenditures",
            json={
                "expenditure_date": "2026-07-05",
                "category": "repairs",
                "description": "Elevator motor replacement",
                "vendor_payee_name": "ABC Elevators Pvt Ltd",
                "amount": "45000.00",
                "payment_mode": "bank_transfer",
                "attachment_s3_key": upload_body["attachment_s3_key"],
            },
        )
        assert create_resp.status_code == 201
        expenditure_id = create_resp.json()["id"]

        attachment_resp = await client.get(
            f"/api/v1/towers/{tower.id}/expenditures/{expenditure_id}/attachment"
        )
        assert attachment_resp.status_code == 200
        get_url = attachment_resp.json()["url"]
        assert get_url

        get_resp = requests.get(get_url, timeout=10)
        assert get_resp.status_code == 200
        assert get_resp.content == b"%PDF-1.4 fake pdf bytes"


@pytest.mark.asyncio
async def test_expenditure_without_attachment_is_valid(client, db_session):
    tower, user = await _setup_tower_with_admin(
        db_session, permission_codes=["MANAGE_EXPENDITURE", "VIEW_TOWER_DATA"]
    )
    await _login(client, user.email)

    resp = await client.post(
        f"/api/v1/towers/{tower.id}/expenditures",
        json={
            "expenditure_date": "2026-07-05",
            "category": "cleaning",
            "description": "Monthly cleaning contract",
            "vendor_payee_name": "Sparkle Services",
            "amount": "5000.00",
            "payment_mode": "cash",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["attachment_s3_key"] is None


@pytest.mark.asyncio
async def test_oversized_attachment_rejected_before_reaching_storage(client, db_session):
    tower, user = await _setup_tower_with_admin(
        db_session, permission_codes=["MANAGE_EXPENDITURE", "VIEW_TOWER_DATA"]
    )
    await _login(client, user.email)

    resp = await client.post(
        f"/api/v1/towers/{tower.id}/expenditures/attachment-upload-url",
        json={
            "filename": "huge.pdf",
            "content_type": "application/pdf",
            "content_length": 11 * 1024 * 1024,
        },
    )
    assert resp.status_code == 413
    assert resp.json()["error_code"] == "ATTACHMENT_TOO_LARGE"

    # No Expenditure row exists referencing a key that was never issued.
    list_resp = await client.get(f"/api/v1/towers/{tower.id}/expenditures")
    assert list_resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_unsupported_attachment_content_type_rejected(client, db_session):
    tower, user = await _setup_tower_with_admin(
        db_session, permission_codes=["MANAGE_EXPENDITURE", "VIEW_TOWER_DATA"]
    )
    await _login(client, user.email)

    resp = await client.post(
        f"/api/v1/towers/{tower.id}/expenditures/attachment-upload-url",
        json={"filename": "invoice.exe", "content_type": "application/x-msdownload"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_complex_contribution_expenditure_appears_in_regular_list_and_totals_correctly(
    client, db_session
):
    tower, user = await _setup_tower_with_admin(
        db_session, permission_codes=["MANAGE_EXPENDITURE", "VIEW_TOWER_DATA"]
    )
    await _login(client, user.email)

    resp = await client.post(
        f"/api/v1/towers/{tower.id}/expenditures/complex-contribution",
        json={
            "expenditure_date": "2026-07-05",
            "description": "Complex-wide painting",
            "vendor_payee_name": "XYZ Painters",
            "complex_total_amount": "500000.00",
            "amount": "80000.00",
            "payment_mode": "cheque",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["is_complex_contribution"] is True
    assert body["complex_total_amount"] == "500000.00"
    assert body["amount"] == "80000.00"
    assert body["category"] == "other"

    list_resp = await client.get(f"/api/v1/towers/{tower.id}/expenditures")
    items = list_resp.json()["items"]
    assert any(i["id"] == body["id"] for i in items)

    # Category/report-style total: only `amount` (the tower's own posted share) is ever
    # summed — `complex_total_amount` must never appear in a SUM()-derived figure.
    total = sum(Decimal(i["amount"]) for i in items)
    assert total == Decimal("80000.00")

    filtered_resp = await client.get(
        f"/api/v1/towers/{tower.id}/expenditures", params={"is_complex_contribution": True}
    )
    filtered_items = filtered_resp.json()["items"]
    assert len(filtered_items) == 1
    assert filtered_items[0]["id"] == body["id"]
