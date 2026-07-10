from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateTowerRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    code: str | None = Field(default=None, min_length=2, max_length=10)
    total_floors: int = Field(gt=0)
    total_flats: int = Field(gt=0)
    association_name: str = Field(min_length=2, max_length=200)


class UpdateTowerRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    total_floors: int | None = Field(default=None, gt=0)
    total_flats: int | None = Field(default=None, gt=0)
    association_name: str | None = Field(default=None, min_length=2, max_length=200)


class TowerOut(BaseModel):
    id: UUID
    complex_id: UUID
    name: str
    code: str
    total_floors: int
    total_flats: int
    association_name: str
    deactivated_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
