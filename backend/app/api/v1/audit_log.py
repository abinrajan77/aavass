from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission
from app.core.pagination import Pagination, pagination_params
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.schemas.audit_log import AuditLogEntryOut
from app.schemas.common import PageEnvelope

router = APIRouter(prefix="/towers/{tower_id}/audit-log", tags=["audit-log"])


@router.get("", response_model=PageEnvelope[AuditLogEntryOut])
async def list_audit_log(
    tower_id: UUID,
    entity_type: str | None = Query(default=None),
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None),
    pagination: Pagination = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("VIEW_REPORTS")),
) -> PageEnvelope[AuditLogEntryOut]:
    conditions = [AuditLog.tower_id == tower_id]
    if entity_type:
        conditions.append(AuditLog.entity_type == entity_type)
    if from_:
        conditions.append(AuditLog.created_at >= from_)
    if to:
        conditions.append(AuditLog.created_at <= to)

    total = await db.scalar(select(func.count()).select_from(AuditLog).where(*conditions))
    rows = (
        (
            await db.execute(
                select(AuditLog)
                .where(*conditions)
                .order_by(AuditLog.created_at.desc())
                .offset(pagination.offset)
                .limit(pagination.page_size)
            )
        )
        .scalars()
        .all()
    )
    return PageEnvelope(
        items=[AuditLogEntryOut.model_validate(r) for r in rows],
        page=pagination.page,
        page_size=pagination.page_size,
        total=total or 0,
    )
