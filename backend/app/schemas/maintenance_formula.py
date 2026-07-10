from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class MaintenanceFormulaCreate(BaseModel):
    base_amount: Decimal = Field(ge=0, decimal_places=2)
    per_sqft_rate: Decimal = Field(ge=0, decimal_places=2)
    effective_from: date | None = None


class MaintenanceFormulaOut(BaseModel):
    id: UUID
    tower_id: UUID
    base_amount: Decimal
    per_sqft_rate: Decimal
    effective_from: date
    created_at: datetime

    model_config = {"from_attributes": True}
