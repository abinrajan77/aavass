"""Seam for Module 2 (Flat/Owner/Tenant) integration.

The equal-split due-generation algorithm in `app.services.special_collection` needs, for a
given tower, every active flat together with its primary *active* owner (never a tenant) if
one exists. `FlatDirectory` is the interface; `get_flat_directory` is the FastAPI dependency
provider routers ask for — `RealFlatDirectory` below is the production implementation, backed
by Module 2's real `flats`/`flat_ownerships`/`owners` tables (this module was originally
written against a placeholder before Module 2 landed; see git history for that version).

Tests supply a concrete implementation (`tests/factories.py`'s `FakeFlatDirectory`) via
`app.dependency_overrides[get_flat_directory]`, the same override pattern already used for
`get_db` in `tests/conftest.py`.
"""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.flat import Flat
from app.models.flat_ownership import FlatOwnership
from app.models.owner import Owner


@dataclass(frozen=True)
class ActiveFlatRecord:
    """One active flat in a tower, as seen by the special-collection due generator.

    `owner_id`/`owner_name` are `None` when the flat has no active owner (e.g. every
    `FlatOwnership` for it has been soft-deleted) — the equal-split algorithm skips such
    flats rather than failing the whole request (backend.md test plan item 3).
    """

    flat_id: UUID
    flat_number: str
    owner_id: UUID | None
    owner_name: str | None


class FlatDirectory(Protocol):
    async def list_active_flats(self, *, tower_id: UUID) -> list[ActiveFlatRecord]:
        """Every active flat in the tower, in no particular order — callers (the equal-split
        generator) are responsible for sorting by `flat_number` themselves."""
        ...


@dataclass(frozen=True)
class RealFlatDirectory:
    """Production `FlatDirectory` backed by Module 2's real tables. "Active" means
    `Flat.deactivated_at IS NULL`; the primary owner (if any) is the `Owner` joined through
    the `FlatOwnership` row where `date_to IS NULL AND is_primary_contact` — the same
    "currently active primary ownership" query Module 3's `flats_service.py` uses."""

    db: AsyncSession

    async def list_active_flats(self, *, tower_id: UUID) -> list[ActiveFlatRecord]:
        rows = (
            await self.db.execute(
                select(Flat, Owner)
                .outerjoin(
                    FlatOwnership,
                    (FlatOwnership.flat_id == Flat.id)
                    & FlatOwnership.date_to.is_(None)
                    & FlatOwnership.is_primary_contact.is_(True),
                )
                .outerjoin(Owner, Owner.id == FlatOwnership.owner_id)
                .where(Flat.tower_id == tower_id, Flat.deactivated_at.is_(None))
            )
        ).all()
        return [
            ActiveFlatRecord(
                flat_id=flat.id,
                flat_number=flat.flat_number,
                owner_id=owner.id if owner is not None else None,
                owner_name=owner.full_name if owner is not None else None,
            )
            for flat, owner in rows
        ]


async def get_flat_directory(db: AsyncSession = Depends(get_db)) -> FlatDirectory:
    """FastAPI dependency provider."""
    return RealFlatDirectory(db=db)
