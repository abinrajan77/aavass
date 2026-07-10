from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateComplexRequest(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    address: str = Field(min_length=2, max_length=500)


class UpdateComplexRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    address: str | None = Field(default=None, min_length=2, max_length=500)


class ComplexOut(BaseModel):
    id: UUID
    name: str
    address: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
