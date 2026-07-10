"""S3 upload / presigned-URL abstraction (`06-cloud-devops.md` §5:
`receipts/{tower_id}/{receipt_id}.pdf`, SSE-S3 encryption, presigned GET with a 15-minute
expiry for downloads).

`boto3` is lazy-imported inside each function, only reached when `settings.s3_bucket` is
configured. When it isn't (local dev, and this sandbox's test runs — no AWS credentials are
available here), both functions fall back to a local-disk directory
(`settings.local_storage_dir`) so the full mark-paid -> render -> "upload" -> download-link
flow can still be exercised end-to-end without any AWS access. Swap in real S3 by setting
`S3_BUCKET`/`AWS_REGION` — no caller-side code changes needed since the function signatures
don't change.
"""

from pathlib import Path

from app.core.config import get_settings

settings = get_settings()

_DEFAULT_PRESIGNED_EXPIRY_SECONDS = 900  # 15 minutes, per 06-cloud-devops.md §5


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
