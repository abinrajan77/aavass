from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateRoleRequest(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    permission_codes: list[str] = Field(min_length=1)


class UpdateRoleRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    permission_codes: list[str] | None = Field(default=None, min_length=1)


class RoleOut(BaseModel):
    id: UUID
    tower_id: UUID
    name: str
    is_system_default: bool
    deactivated_at: datetime | None
    created_at: datetime
    permission_codes: list[str] = []

    model_config = {"from_attributes": True}
