"""Shared audit-log write helper — used directly by this module, imported by Modules 3/4.

Per backend.md: the caller commits as part of the same transaction as the entity write; the
audit row and entity change must be atomic. This function only calls `db.add()` — it never
calls `db.commit()` itself, so it participates in whatever transaction the caller is already
inside.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.user import User


async def write_audit_log(
    db: AsyncSession,
    *,
    actor: User,
    tower_id: UUID | None,
    action: str,
    entity_type: str,
    entity_id: UUID,
    before: dict | None,
    after: dict | None,
    actor_label: str | None = None,
) -> None:
    db.add(
        AuditLog(
            tower_id=tower_id,
            user_id=actor.id,
            actor_label=actor_label or actor.email,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before=before,
            after=after,
        )
    )
