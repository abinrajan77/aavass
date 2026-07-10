from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class OwnerSummary(BaseModel):
    """Embedded in `FlatOut.primary_owner` and `FlatOwnershipOut.owner`.

    `user_id` is included so the frontend can match `owner.user_id == session.user.id` to
    identify "my own" contact record on the owner self-service surface (`/my-flats/[flatId]`)
    without a separate lookup.
    """

    id: UUID
    user_id: UUID | None
    full_name: str
    phone: str
    email: str | None

    model_config = ConfigDict(from_attributes=True)


class OwnerOut(BaseModel):
    id: UUID
    user_id: UUID | None
    full_name: str
    phone: str
    email: str | None
    id_number: str | None
    deactivated_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OwnerContactUpdate(BaseModel):
    """The ONLY fields a `MANAGE_OWN_FLAT` caller may write on their own `Owner` record —
    `full_name`/`id_number` require `MANAGE_RESIDENTS` (see `OwnerFullUpdate`). `extra="forbid"`
    means a raw API call smuggling an extra field (e.g. `full_name`) is rejected at the schema
    layer before it ever reaches the router/service.
    """

    model_config = ConfigDict(extra="forbid")

    phone: str | None = None
    email: EmailStr | None = None


class OwnerFullUpdate(OwnerContactUpdate):
    """Superset accepted from `MANAGE_RESIDENTS` callers."""

    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    id_number: str | None = Field(default=None, max_length=50)


class FlatOwnershipCreateRequest(BaseModel):
    """Body for `POST .../flats/{flat_id}/owners`. Either references an existing global
    `Owner` via `owner_id`, or creates a brand-new one inline from `full_name`/`phone`/etc.
    """

    owner_id: UUID | None = None
    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    phone: str | None = Field(default=None, min_length=6, max_length=20)
    email: EmailStr | None = None
    id_number: str | None = Field(default=None, max_length=50)
    is_primary_contact: bool = False
    date_from: date

    @model_validator(mode="after")
    def check_owner_source(self) -> "FlatOwnershipCreateRequest":
        if self.owner_id is None and (not self.full_name or not self.phone):
            raise ValueError(
                "full_name and phone are required to create a new owner when owner_id is not "
                "provided"
            )
        return self


class FlatOwnershipUpdate(BaseModel):
    """Body for `PATCH .../flats/{flat_id}/owners/{ownership_id}` — flips which ownership row
    is the flat's primary contact. Setting `is_primary_contact=true` atomically demotes the
    flat's current primary contact (if any) in the same transaction.
    """

    is_primary_contact: bool | None = None
    new_primary_owner_id: UUID | None = None


class OwnerRemoveRequest(BaseModel):
    """Body for `POST .../flats/{flat_id}/owners/{ownership_id}/remove`."""

    effective_date: date
    new_primary_owner_id: UUID | None = None


class FlatOwnershipOut(BaseModel):
    id: UUID
    flat_id: UUID
    owner_id: UUID
    is_primary_contact: bool
    date_from: date
    date_to: date | None
    created_at: datetime
    owner: OwnerSummary | None = None

    model_config = ConfigDict(from_attributes=True)
