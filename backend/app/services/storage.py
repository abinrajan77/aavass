"""S3 upload / presigned-URL abstraction (`06-cloud-devops.md` §5). Two upload flows live here:

- **Receipts (Module 3)** — `upload_bytes()` / `presigned_get_url()`: the backend renders the
  PDF itself and pushes the bytes to S3 server-side (`receipts/{tower_id}/{receipt_id}.pdf`).
  `boto3` is lazy-imported, only reached when `settings.s3_bucket` is configured; when it isn't
  (local dev, and this sandbox's test runs — no AWS credentials available here), both
  functions fall back to a local-disk directory (`settings.local_storage_dir`) so the full
  mark-paid -> render -> "upload" -> download-link flow can still be exercised end-to-end
  without any AWS access.
- **Expenditure attachments (Module 4)** — `build_expenditure_attachment_key()` /
  `generate_attachment_put_url()` / `generate_get_url()`: the client uploads directly via a
  presigned PUT URL (`expenditure-attachments/{tower_id}/{expenditure_id}/{filename}`), so the
  backend never receives the file bytes — exercised against a real (moto-mocked) S3 API in
  that module's own tests, hence no local-disk fallback here.

Both flows implement the same "backend generates a pre-signed PUT/GET URL, the frontend never
gets long-lived S3 credentials" pattern from `06-cloud-devops.md` §5; they weren't unified into
one code path since they upload in opposite directions (server-push vs. client-push).
"""

from pathlib import Path
from uuid import UUID

from app.core.config import get_settings

settings = get_settings()

_DEFAULT_PRESIGNED_EXPIRY_SECONDS = 900  # 15 minutes, per 06-cloud-devops.md §5

# content_type -> allowed (backend.md: "PDF/JPEG/PNG only")
ALLOWED_ATTACHMENT_CONTENT_TYPES = {"application/pdf", "image/jpeg", "image/png"}
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024  # 10 MB, per backend.md
DEFAULT_URL_EXPIRY_SECONDS = _DEFAULT_PRESIGNED_EXPIRY_SECONDS


async def upload_bytes(*, key: str, data: bytes, content_type: str) -> None:
    if not settings.s3_bucket:
        path = Path(settings.local_storage_dir) / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return

    import boto3  # lazy: only required when S3 is actually configured

    client = boto3.client("s3", region_name=settings.aws_region)
    client.put_object(
        Bucket=settings.s3_bucket,
        Key=key,
        Body=data,
        ContentType=content_type,
        ServerSideEncryption="AES256",
    )


async def presigned_get_url(
    *, key: str, expires_in: int = _DEFAULT_PRESIGNED_EXPIRY_SECONDS
) -> str:
    if not settings.s3_bucket:
        return f"file://{(Path(settings.local_storage_dir) / key).resolve()}"

    import boto3  # lazy: only required when S3 is actually configured

    client = boto3.client("s3", region_name=settings.aws_region)
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": key},
        ExpiresIn=expires_in,
    )


def _s3_client():
    import boto3
    from botocore.client import Config

    current_settings = get_settings()
    client_kwargs: dict = {
        "region_name": current_settings.aws_region,
        "config": Config(signature_version="s3v4"),
    }
    # Only set for local/test (moto, localstack) — never set in prod, where boto3 talks to
    # real AWS S3 directly.
    if current_settings.s3_endpoint_url:
        client_kwargs["endpoint_url"] = current_settings.s3_endpoint_url
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
    current_settings = get_settings()
    client = _s3_client()
    return client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": current_settings.s3_bucket_name,
            "Key": s3_key,
            "ContentType": content_type,
        },
        ExpiresIn=expires_in,
    )


def generate_get_url(*, s3_key: str, expires_in: int = DEFAULT_URL_EXPIRY_SECONDS) -> str:
    current_settings = get_settings()
    client = _s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": current_settings.s3_bucket_name, "Key": s3_key},
        ExpiresIn=expires_in,
    )
