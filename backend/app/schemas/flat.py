from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.owner import OwnerSummary
from app.schemas.tenant import TenantSummary

FlatType = Literal["1BHK", "2BHK", "3BHK", "OTHER"]
OccupancyStatus = Literal["owner_occupied", "tenant_occupied", "vacant"]


class FlatCreate(BaseModel):
    flat_number: str = Field(min_length=1, max_length=20)
    floor: int
    type: FlatType
    carpet_area_sqft: Decimal = Field(gt=0)


class FlatUpdate(BaseModel):
    """`occupancy_status` is deliberately absent — it is only ever changed via the tenant
    create/vacate service functions (see `specs/02-flat-owner-tenant/backend.md`)."""

    flat_number: str | None = Field(default=None, min_length=1, max_length=20)
    floor: int | None = None
    type: FlatType | None = None
    carpet_area_sqft: Decimal | None = Field(default=None, gt=0)


class FlatOut(BaseModel):
    id: UUID
    tower_id: UUID
    flat_number: str
    floor: int
    type: str
    carpet_area_sqft: Decimal
    occupancy_status: OccupancyStatus
    primary_owner: OwnerSummary | None
    active_tenant: TenantSummary | None
    deactivated_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
