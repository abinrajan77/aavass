"""Seam for Module 2 (Flat/Owner/Tenant) integration.

Module 2's `Flat`/`Owner`/`FlatOwnership`/`Tenant` tables don't exist yet in this codebase
(see `specs/04-special-collections-expenditure/backend.md`'s scope note and
`specs/00-architecture-and-standards.md` §2 dependency order). The equal-split due-generation
algorithm in `app.services.special_collection` needs, for a given tower, every active flat
together with its primary *active* owner (never a tenant) if one exists.

This module is the single integration point for that data. `FlatDirectory` is the interface;
`get_flat_directory` is the FastAPI dependency provider routers ask for. Once Module 2 ships,
swap the object returned by `get_flat_directory` for one backed by real
`flats`/`flat_ownerships`/`owners` queries — no other file in this module (router or service)
needs to change.

Tests supply a concrete implementation (`tests/factories.py`'s `FakeFlatDirectory`) via
`app.dependency_overrides[get_flat_directory]`, the same override pattern already used for
`get_db` in `tests/conftest.py`.
"""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.core.errors import AppError


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


class Module2NotIntegratedFlatDirectory:
    """Production placeholder used until Module 2 (Flat/Owner/Tenant) lands. Raises a clear,
    typed error rather than silently fabricating flat data or returning an empty list (which
    would look like "zero active flats" instead of "this feature isn't wired up yet")."""

    async def list_active_flats(self, *, tower_id: UUID) -> list[ActiveFlatRecord]:
        raise AppError(
            501,
            "FLAT_DIRECTORY_NOT_AVAILABLE",
            "Special collection due generation requires Module 2 (Flat/Owner) integration, "
            "which has not been implemented in this codebase yet.",
        )


async def get_flat_directory() -> FlatDirectory:
    """FastAPI dependency provider — see module docstring for the swap-in-Module-2 plan."""
    return Module2NotIntegratedFlatDirectory()
