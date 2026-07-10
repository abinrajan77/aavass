from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: UUID
    email: str
    account_type: str
    is_superuser: bool

    model_config = {"from_attributes": True}


class TowerMembership(BaseModel):
    tower_id: UUID
    tower_name: str
    role_name: str


class LoginResponse(BaseModel):
    user: UserOut
    permissions: list[str]
    towers: list[TowerMembership]


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class MeResponse(BaseModel):
    user: UserOut
    permissions: list[str]
    towers: list[TowerMembership]
