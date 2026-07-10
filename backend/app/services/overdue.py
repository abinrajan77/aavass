"""Overdue transition — backend.md §3 design decision: a daily scheduled job, not an on-read
computed check (see that section for the full rationale: list/dashboard latency budgets, a
single clear audit-write point, and day-granularity freshness being sufficient).

This module implements the job *body* only (`run_overdue_transition`), independent of whatever
invokes it on a schedule. `backend/app/worker/overdue_job.py` is a thin `main()` entrypoint
meant to be triggered by an external scheduler (cron / ECS Scheduled Task at 00:15 UTC per
backend.md §3) — this repo does not embed Celery beat/APScheduler itself, since neither is a
dependency anywhere else in the codebase yet; adding one is an infra decision for whoever wires
up the actual ECS worker service, not a change to this module's business logic.
"""

from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing_cycle import BillingCycle
from app.models.maintenance_due import MaintenanceDue
from app.services.audit import write_audit_log

SYSTEM_ACTOR_LABEL = "system:overdue-transition-job"


def is_overdue(due_date: date, grace_period_days: int, as_of: date) -> bool:
    """`due_date + grace_period_days` has *passed* — a grace period of 0 means Overdue the day
    after the due date (overview.md edge case 2), not on the due date itself."""
    return as_of > due_date + timedelta(days=grace_period_days)


async def run_overdue_transition(db: AsyncSession, *, as_of: date | None = None) -> list[UUID]:
    """Flips every `Pending` due whose `due_date + billing_cycle.grace_period_days_snapshot`
    has passed to `Overdue`, across all towers in one pass, and writes one `audit_log` row per
    flipped due (`action='due_overdue_transition'`, system-generated: no `user_id`).

    Idempotent: only ever touches rows still `status='pending'` as of the moment it runs, so
    re-running it twice in a day (or being retried after a partial failure) never re-flips an
    already-Overdue or Paid due, and never double-writes an audit row for the same transition
    (backend.md §8.3 regression list).

    Returns the list of due IDs that were flipped, for logging/testing convenience.
    """
    as_of = as_of or date.today()

    rows = (
        await db.execute(
            select(MaintenanceDue, BillingCycle.grace_period_days_snapshot)
            .join(BillingCycle, BillingCycle.id == MaintenanceDue.billing_cycle_id)
            .where(MaintenanceDue.status == "pending")
        )
    ).all()

    flipped: list[UUID] = []
    for due, grace_period_days in rows:
        if not is_overdue(due.due_date, grace_period_days, as_of):
            continue
        due.status = "overdue"
        await write_audit_log(
            db,
            actor=None,
            actor_label=SYSTEM_ACTOR_LABEL,
            tower_id=due.tower_id,
            action="due_overdue_transition",
            entity_type="maintenance",
            entity_id=due.id,
            before={"status": "pending"},
            after={"status": "overdue"},
        )
        flipped.append(due.id)

    await db.commit()
    return flipped
