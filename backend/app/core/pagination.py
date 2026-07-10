"""Offset pagination dependency — enforces page_size max 100 via FastAPI/Pydantic validation
(422 on violation, never silently clamped, per overview.md edge case)."""

from dataclasses import dataclass

from fastapi import Query

from app.schemas.common import MAX_PAGE_SIZE


@dataclass
class Pagination:
    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def pagination_params(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=MAX_PAGE_SIZE),
) -> Pagination:
    return Pagination(page=page, page_size=page_size)
