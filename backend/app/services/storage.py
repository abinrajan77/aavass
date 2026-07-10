"""S3 pre-signed URL helpers — shared upload/download pattern per
`../06-cloud-devops.md` §5 ("backend generates a pre-signed PUT URL for uploads ... and
pre-signed GET URLs for downloads ... the frontend never gets long-lived S3 credentials").
This module owns expenditure attachments; Module 3 (receipts) will reuse the same pattern
under its own `receipts/{tower_id}/{receipt_id}.pdf` prefix.
"""

from uuid import UUID

import boto3
from botocore.client import Config

from app.core.config import get_settings

# content_type -> allowed (backend.md: "PDF/JPEG/PNG only")
ALLOWED_ATTACHMENT_CONTENT_TYPES = {"application/pdf", "image/jpeg", "image/png"}
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024  # 10 MB, per backend.md
DEFAULT_URL_EXPIRY_SECONDS = 900  # 15 minutes


def _s3_client():
    settings = get_settings()
    client_kwargs: dict = {
        "region_name": settings.aws_region,
        "config": Config(signature_version="s3v4"),
    }
    # Only set for local/test (moto, localstack) — never set in prod, where boto3 talks to
    # real AWS S3 directly.
    if settings.s3_endpoint_url:
        client_kwargs["endpoint_url"] = settings.s3_endpoint_url
    return boto3.client("s3", **client_kwargs)


def build_expenditure_attachment_key(*, tower_id: UUID, attachment_id: UUID, filename: str) -> str:
    """Matches the prefix convention in `cloud.md`:
    `expenditure-attachments/{tower_id}/{expenditure_id}/{filename}`. The attachment is
    uploaded *before* the `Expenditure` row exists (client calls this endpoint, then
    references the returned key in the create/edit call), so `attachment_id` is a freshly
    minted UUID standing in for the eventual expenditure id, not a real FK — the same
    "mint an id before the owning row exists" pattern Module 3 uses for receipt PDFs."""
    return f"expenditure-attachments/{tower_id}/{attachment_id}/{filename}"


def generate_attachment_put_url(
    *, s3_key: str, content_type: str, expires_in: int = DEFAULT_URL_EXPIRY_SECONDS
) -> str:
    settings = get_settings()
    client = _s3_client()
    return client.generate_presigned_url(
        "put_object",
        Params={"Bucket": settings.s3_bucket_name, "Key": s3_key, "ContentType": content_type},
        ExpiresIn=expires_in,
    )


def generate_get_url(*, s3_key: str, expires_in: int = DEFAULT_URL_EXPIRY_SECONDS) -> str:
    settings = get_settings()
    client = _s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket_name, "Key": s3_key},
        ExpiresIn=expires_in,
    )
