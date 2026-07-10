"""Password hashing (argon2id), JWT access tokens (HS256), and opaque refresh/reset tokens."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import get_settings

settings = get_settings()

# argon2id is the default type for argon2-cffi's PasswordHasher.
_password_hasher = PasswordHasher()


def hash_password(plain_password: str) -> str:
    return _password_hasher.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return _password_hasher.verify(hashed_password, plain_password)
    except VerifyMismatchError:
        return False
    except Exception:
        # Malformed/legacy hash, unknown algorithm, etc. — never raise out of an auth check.
        return False


def create_access_token(*, user_id: UUID, extra_claims: dict | None = None) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
        "type": "access",
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.jwt_signing_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_signing_key, algorithms=[settings.jwt_algorithm])


def generate_opaque_token() -> str:
    """256-bit random value, URL-safe encoded. Used for refresh tokens and password-reset
    tokens — never stored in plaintext, only its SHA-256 hash (see `hash_token`)."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def refresh_token_expiry() -> datetime:
    return datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)


def password_reset_token_expiry() -> datetime:
    return datetime.now(UTC) + timedelta(hours=1)
