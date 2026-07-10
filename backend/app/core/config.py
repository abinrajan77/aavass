"""Application settings, loaded from environment variables (.env in local dev)."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    env: str = Field(default="local", alias="ENV")
    debug: bool = Field(default=True, alias="DEBUG")

    # --- Database ---
    database_url: str = Field(
        default="postgresql+asyncpg://aavaas:aavaas@localhost:5432/aavaas",
        alias="DATABASE_URL",
    )

    # --- JWT / Auth ---
    jwt_signing_key: str = Field(default="dev-only-insecure-signing-key", alias="JWT_SIGNING_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=15, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=30, alias="REFRESH_TOKEN_EXPIRE_DAYS")

    # --- Cookies ---
    cookie_secure: bool = Field(default=False, alias="COOKIE_SECURE")
    cookie_domain: str | None = Field(default=None, alias="COOKIE_DOMAIN")

    # --- CORS ---
    cors_origins: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")

    # --- AWS (S3 receipts, SQS billing-cycle-jobs) — 06-cloud-devops.md §4/§5 ---
    # Both `s3_bucket` and `sqs_queue_url` default to unset: local dev/test runs never talk to
    # real AWS. `app.services.storage` falls back to writing PDFs under `local_storage_dir`
    # when `s3_bucket` is unset; `app.services.sqs` no-ops the enqueue (the `jobs` row created
    # in the same DB transaction is the actual source of truth polled by the client either way)
    # when `sqs_queue_url` is unset. Set both in staging/prod task definitions via Secrets
    # Manager/SSM per `06-cloud-devops.md` §3.
    aws_region: str = Field(default="ap-south-1", alias="AWS_REGION")
    s3_bucket: str | None = Field(default=None, alias="S3_BUCKET")
    sqs_queue_url: str | None = Field(default=None, alias="SQS_BILLING_CYCLE_QUEUE_URL")
    local_storage_dir: str = Field(default="./local_storage", alias="LOCAL_STORAGE_DIR")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
