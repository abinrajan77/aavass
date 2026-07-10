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

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
