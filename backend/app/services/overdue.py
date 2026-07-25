"""Overdue transition — backend.md §3 design decision: a daily scheduled job, not an on-read
computed check (see that section for the full rationale: list/dashboard latency budgets, a
single clear audit-write point, and day-granularity freshness being sufficient).

Also handles `special_collection_dues` (`specs/04-special-collections-expenditure/backend.md`:
"transitions to overdue via the shared scheduled job ... keyed off each tower's grace-period
config" — reusing this job, not building a second scheduler). Unlike `maintenance_dues`,
special-collection dues have no per-due grace-period snapshot (no billing cycle to snapshot it
from), so this looks up each affected tower's *current* `GracePeriodConfig` instead.

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
from app.models.special_collection import SpecialCollection
from app.models.special_collection_due import SpecialCollectionDue
from app.services.audit import write_audit_log
from app.services.billing_formula import get_current_grace_period

SYSTEM_ACTOR_LABEL = "system:overdue-transition-job"


def is_overdue(due_date: date, grace_period_days: int, as_of: date) -> bool:
    """`due_date + grace_period_days` has *passed* — a grace period of 0 means Overdue the day
    after the due date (overview.md edge case 2), not on the due date itself."""
    return as_of > due_date + timedelta(days=grace_period_days)


async def _transition_maintenance_dues(db: AsyncSession, *, as_of: date) -> list[UUID]:
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
    return flipped


async def _transition_special_collection_dues(db: AsyncSession, *, as_of: date) -> list[UUID]:
    # Cancelled collections' leftover `pending` rows aren't money actually owed anymore (see
    # app.services.tower.tower_has_active_financials) — never transition those to overdue.
    rows = (
        await db.execute(
            select(SpecialCollectionDue).where(
                SpecialCollectionDue.status == "pending",
                SpecialCollectionDue.special_collection_id.in_(
                    select(SpecialCollection.id).where(SpecialCollection.deactivated_at.is_(None))
                ),
            )
        )
    ).scalars().all()

    grace_period_by_tower: dict[UUID, int] = {}
    flipped: list[UUID] = []
    for due in rows:
        if due.tower_id not in grace_period_by_tower:
            config = await get_current_grace_period(db, due.tower_id, as_of)
            grace_period_by_tower[due.tower_id] = config.grace_period_days if config else 0
        if not is_overdue(due.due_date, grace_period_by_tower[due.tower_id], as_of):
            continue
        due.status = "overdue"
        await write_audit_log(
            db,
            actor=None,
            actor_label=SYSTEM_ACTOR_LABEL,
            tower_id=due.tower_id,
            action="due_overdue_transition",
            entity_type="special_collection",
            entity_id=due.id,
            before={"status": "pending"},
            after={"status": "overdue"},
        )
        flipped.append(due.id)
    return flipped


async def run_overdue_transition(db: AsyncSession, *, as_of: date | None = None) -> list[UUID]:
    """Flips every `Pending` maintenance/special-collection due whose grace period has elapsed
    to `Overdue`, across all towers in one pass, and writes one `audit_log` row per flipped due
    (`action='due_overdue_transition'`, system-generated: no `user_id`).

    Idempotent: only ever touches rows still `status='pending'` as of the moment it runs, so
    re-running it twice in a day (or being retried after a partial failure) never re-flips an
    already-Overdue or Paid due, and never double-writes an audit row for the same transition
    (backend.md §8.3 regression list).

    Returns the list of due IDs that were flipped, for logging/testing convenience.
    """
    as_of = as_of or date.today()

    flipped = await _transition_maintenance_dues(db, as_of=as_of)
    flipped += await _transition_special_collection_dues(db, as_of=as_of)

    await db.commit()
    return flipped
