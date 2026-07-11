"""Notification template preview — backend.md §4. `require_permission("VIEW_REPORTS")` is
reused to gate this (per `00-architecture-and-standards.md` §7: "no dedicated notifications
permission exists in the catalog"), but this route has no `tower_id` path param (it's
`/api/v1/notifications/templates/preview`, not tower-nested) — `tower_id` is instead derived
from the resolved due itself, so the permission check below re-implements
`require_permission`'s body against that derived tower_id rather than a `Path(...)` binding."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.deps import get_current_user
from app.core.errors import AppError
from app.db.session import get_db
from app.models.association_member import AssociationMember
from app.models.role import Role
from app.models.user import User
from app.schemas.notification import NotificationEvent, NotificationPreviewResponse
from app.services.notifications import build_notification_messages, resolve_due_context

router = APIRouter(prefix="/notifications", tags=["notifications"])


async def _require_view_reports(db: AsyncSession, *, current_user: User, tower_id: UUID) -> None:
    """Same enforcement as `app.api.deps.require_permission("VIEW_REPORTS")`, parameterized by a
    `tower_id` resolved from the due rather than a path parameter (see module docstring)."""
    if current_user.is_superuser:
        return

    member = await db.scalar(
        select(AssociationMember)
        .where(
            AssociationMember.user_id == current_user.id,
            AssociationMember.tower_id == tower_id,
            AssociationMember.deactivated_at.is_(None),
        )
        .options(joinedload(AssociationMember.role).joinedload(Role.permissions))
    )
    if member is None:
        raise AppError(403, "TOWER_ACCESS_DENIED", "You do not have access to this tower.")
    if member.role.deactivated_at is not None:
        raise AppError(403, "ROLE_INACTIVE", "Your role has been deactivated.")
    granted_codes = {p.code for p in member.role.permissions}
    if "VIEW_REPORTS" not in granted_codes:
        raise AppError(403, "PERMISSION_DENIED", "Missing required permission: VIEW_REPORTS.")


@router.get("/templates/preview", response_model=NotificationPreviewResponse)
async def preview_notification(
    event: NotificationEvent = Query(...),
    due_id: UUID = Query(...),
    due_type: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationPreviewResponse:
    context = await resolve_due_context(db, due_type=due_type, due_id=due_id)
    await _require_view_reports(db, current_user=current_user, tower_id=context.tower_id)

    messages = await build_notification_messages(db, event=event, context=context)
    return NotificationPreviewResponse(
        event=event, due_id=due_id, flat_number=context.flat_number, messages=messages
    )
