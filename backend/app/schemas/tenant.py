from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, ValidationInfo, field_validator


class TenantSummary(BaseModel):
    """Embedded in `FlatOut.active_tenant`."""

    id: UUID
    full_name: str
    phone: str
    lease_start: date

    model_config = ConfigDict(from_attributes=True)


class TenantCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    phone: str = Field(min_length=6, max_length=20)
    email: EmailStr | None = None
    id_number: str | None = Field(default=None, max_length=50)
    lease_start: date
    lease_end: date | None = None

    # A `field_validator` on `lease_end` (rather than backend.md's literal
    # `model_validator(mode="after")`) so the resulting `422` attributes the error to the
    # `lease_end` field specifically (`field_errors={"lease_end": ...}`) instead of the whole
    # request body — required by backend.md's own integration test plan ("returns 422 with a
    # field_errors entry for lease_end"). Cross-field access via `info.data` (already-validated
    # `lease_start`) gives the identical validation rule.
    @field_validator("lease_end")
    @classmethod
    def check_lease_end_not_before_lease_start(
        cls, v: date | None, info: ValidationInfo
    ) -> date | None:
        lease_start = info.data.get("lease_start")
        if v is not None and lease_start is not None and v < lease_start:
            raise ValueError("lease_end must not be before lease_start")
        return v


class TenantUpdate(BaseModel):
    """Corrections to phone/email/lease_end while still active — never touches `is_active`."""

    phone: str | None = Field(default=None, min_length=6, max_length=20)
    email: EmailStr | None = None
    lease_end: date | None = None


class TenantVacate(BaseModel):
    vacated_date: date
    occupancy_status: Literal["owner_occupied", "vacant"]


class TenantOut(BaseModel):
    id: UUID
    flat_id: UUID
    full_name: str
    phone: str
    email: str | None
    id_number: str | None
    lease_start: date
    lease_end: date | None
    is_active: bool
    vacated_at: datetime | None
    created_at: datetime
    deactivated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
