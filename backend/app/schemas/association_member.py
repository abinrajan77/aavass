from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class CreateAssociationMemberRequest(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    phone: str = Field(pattern=r"^[6-9]\d{9}$")
    role_id: UUID


class UpdateAssociationMemberRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    phone: str | None = Field(default=None, pattern=r"^[6-9]\d{9}$")
    role_id: UUID | None = None


class AssociationMemberOut(BaseModel):
    id: UUID
    tower_id: UUID
    user_id: UUID
    role_id: UUID
    name: str
    phone: str
    deactivated_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CreateAssociationMemberResponse(BaseModel):
    association_member: AssociationMemberOut
    temporary_password: str  # shown once; not retrievable again
