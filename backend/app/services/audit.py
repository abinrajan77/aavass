"""Shared audit-log write helper — used directly by this module, imported by Modules 3/4.

Per backend.md: the caller commits as part of the same transaction as the entity write; the
audit row and entity change must be atomic. This function only calls `db.add()` — it never
calls `db.commit()` itself, so it participates in whatever transaction the caller is already
inside.

`actor=None` supports system-generated entries (e.g. Module 3's nightly overdue-transition
job, per `00-architecture-and-standards.md` §6: "`tower_id`/`user_id` are nullable to allow
complex-level and system-generated entries") — callers passing `actor=None` must supply
`actor_label` explicitly since there is no `User` to derive it from.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.user import User


async def write_audit_log(
    db: AsyncSession,
    *,
    actor: User | None,
    tower_id: UUID | None,
    action: str,
    entity_type: str,
    entity_id: UUID,
    before: dict | None,
    after: dict | None,
    actor_label: str | None = None,
) -> None:
    if actor is None and actor_label is None:
        raise ValueError("write_audit_log: actor_label is required when actor is None.")
    db.add(
        AuditLog(
            tower_id=tower_id,
            user_id=actor.id if actor is not None else None,
            actor_label=actor_label or actor.email,  # type: ignore[union-attr]
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before=before,
            after=after,
        )
    )
