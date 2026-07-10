from typing import Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.errors import AppError
from app.db.session import get_db
from app.models.user import User
from app.schemas.owner import OwnerContactUpdate, OwnerFullUpdate, OwnerOut
from app.services.audit import write_audit_log
from app.services.owner import resolve_owner_access

router = APIRouter(prefix="/owners", tags=["owners"])


def _parse_scoped_payload(scope: str, raw_body: dict[str, Any]) -> OwnerContactUpdate:
    schema_cls = OwnerFullUpdate if scope == "manage" else OwnerContactUpdate
    try:
        return schema_cls.model_validate(raw_body)
    except ValidationError as exc:
        field_errors: dict[str, str] = {}
        for err in exc.errors():
            loc = ".".join(str(p) for p in err["loc"]) or "__root__"
            field_errors[loc] = err["msg"]
        raise AppError(
            422, "VALIDATION_ERROR", "Request validation failed.", field_errors=field_errors
        ) from None


@router.patch("/{owner_id}", response_model=OwnerOut)
async def update_owner(
    owner_id: UUID,
    raw_body: dict[str, Any] = Body(default_factory=dict),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OwnerOut:
    """Global (non-tower-scoped) route since `Owner` spans towers. `MANAGE_RESIDENTS` callers
    (resolved against any tower where this owner currently holds a `FlatOwnership`) may edit
    every field via `OwnerFullUpdate`; the owner editing their own record is restricted to
    `OwnerContactUpdate` (`phone`/`email` only, `extra="forbid"`) — parsed against the narrower
    schema for that scope so a self-caller can never smuggle `full_name`/`id_number` through
    even via a raw API call (see `specs/02-flat-owner-tenant/overview.md` edge case).
    """
    owner, scope = await resolve_owner_access(db, owner_id=owner_id, current_user=current_user)
    payload = _parse_scoped_payload(scope, raw_body)

    before = {
        "full_name": owner.full_name,
        "phone": owner.phone,
        "email": owner.email,
        "id_number": owner.id_number,
    }
    if payload.phone is not None:
        owner.phone = payload.phone
    if payload.email is not None:
        owner.email = payload.email
    if isinstance(payload, OwnerFullUpdate):
        if payload.full_name is not None:
            owner.full_name = payload.full_name
        if payload.id_number is not None:
            owner.id_number = payload.id_number
    after = {
        "full_name": owner.full_name,
        "phone": owner.phone,
        "email": owner.email,
        "id_number": owner.id_number,
    }

    await write_audit_log(
        db,
        actor=current_user,
        tower_id=None,
        action="OWNER_UPDATED",
        entity_type="Owner",
        entity_id=owner.id,
        before=before,
        after=after,
    )
    await db.commit()
    await db.refresh(owner)
    return OwnerOut.model_validate(owner)
