from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class BillingCycleCreate(BaseModel):
    month: int = Field(ge=1, le=12)
    year: int = Field(ge=2020, le=2100)
    due_date: date


class BillingCycleUpdate(BaseModel):
    due_date: date


class BillingCycleOut(BaseModel):
    id: UUID
    tower_id: UUID
    month: int
    year: int
    due_date: date
    status: Literal["generating", "active"]
    formula_id: UUID
    grace_period_days_snapshot: int
    created_at: datetime
    total_dues: int
    total_collected: Decimal
    pending_count: int
    overdue_count: int
    # Deviation from backend.md §7's minimal schema: surfaces per-flat generation failures
    # (overview.md edge case 12 — e.g. NO_PRIMARY_OWNER) on the sync-generation response so a
    # cycle can be created "successfully" while a handful of flats still need admin attention,
    # without inventing a separate endpoint just to expose them.
    generation_failures: list[dict] | None = None

    model_config = {"from_attributes": True}


class BillingCycleAcceptedOut(BaseModel):
    """202 response for the async (>300 active flats) generation path."""

    cycle_id: UUID
    job_id: UUID
    status: Literal["generating"] = "generating"
