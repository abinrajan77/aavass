from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class SplitBasis(str, Enum):
    equal = "equal"


class SpecialCollectionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    total_amount: Decimal = Field(gt=0, decimal_places=2)
    split_basis: SplitBasis = SplitBasis.equal
    due_date: date


class SkippedFlat(BaseModel):
    flat_id: UUID
    flat_number: str
    reason: Literal["NO_ACTIVE_OWNER"]


class SpecialCollectionOut(BaseModel):
    id: UUID
    tower_id: UUID
    title: str
    description: str | None
    total_amount: Decimal
    split_basis: SplitBasis
    due_date: date
    dues_generated_at: datetime | None
    # True once dues exist for this collection — the sync path always sets this True in the
    # same response (backend.md's async >300-flats path, where this would be False, is not
    # implemented in this slice; see app/services/special_collection.py).
    dues_generated: bool
    skipped_flats: list[SkippedFlat]
    collected_amount: Decimal
    pending_count: int
    paid_count: int
    overdue_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class SpecialCollectionDueOut(BaseModel):
    id: UUID
    special_collection_id: UUID
    flat_id: UUID
    flat_number: str  # snapshotted from Module 2 Flat at generation time — see model docstring
    owner_id: UUID
    owner_name: str  # snapshotted from Module 2 Owner at generation time — see model docstring
    amount: Decimal
    due_date: date
    status: Literal["pending", "paid", "overdue"]

    model_config = {"from_attributes": True}
