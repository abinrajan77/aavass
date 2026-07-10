from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class GracePeriodConfigCreate(BaseModel):
    grace_period_days: int = Field(ge=0)
    effective_from: date | None = None


class GracePeriodConfigOut(BaseModel):
    id: UUID
    tower_id: UUID
    grace_period_days: int
    effective_from: date
    created_at: datetime

    model_config = {"from_attributes": True}
