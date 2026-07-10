"""Shared envelope schemas: RFC7807-style errors and offset pagination."""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")

MAX_PAGE_SIZE = 100


class ProblemDetail(BaseModel):
    error_code: str
    message: str
    field_errors: dict[str, str] | None = None


class PageParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=MAX_PAGE_SIZE)


class PageEnvelope(BaseModel, Generic[T]):
    items: list[T]
    page: int
    page_size: int
    total: int
