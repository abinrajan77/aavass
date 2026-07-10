"""Billing-cycle generation (backend.md §4) and due-assignment logic (backend.md §5). Both the
sync (<=300 active flats) and async (SQS worker) paths call the exact same
`_generate_dues_for_cycle()` so formula calc + assignment behave identically regardless of
scale — see `create_cycle_row` / `generate_dues_sync` (sync path, called directly from the
router) and `process_billing_cycle_job` (async path, called by the worker or, in this sandbox
without a real SQS consumer, directly by a caller simulating "the worker picked this up").
"""

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.billing_cycle import BillingCycle
from app.models.job import Job
from app.models.maintenance_due import MaintenanceDue
from app.models.maintenance_formula import MaintenanceFormula
from app.services import flats_service
from app.services import jobs as jobs_service
from app.services.billing_formula import (
    calculate_monthly_maintenance,
    get_current_formula,
    get_current_grace_period,
)
from app.services.flats_service import FlatRead

SYNC_GENERATION_FLAT_THRESHOLD = 300


class DueGenerationError(Exception):
    """Per-flat failure during due generation — does not abort the whole cycle
    (overview.md edge case 12; backend.md §5)."""

    def __init__(self, flat_id: UUID, reason: str):
        self.flat_id = flat_id
        self.reason = reason
        super().__init__(f"Due generation failed for flat {flat_id}: {reason}")


@dataclass(frozen=True)
class GenerationFailure:
    flat_id: str
    reason: str


async def assign_due(flat: FlatRead) -> tuple[str, UUID, str]:
    """backend.md §5, verbatim: tenant-occupied flats with an active tenant are assigned to
    that tenant; every other case (owner-occupied, vacant) falls to the flat's primary owner,
    raising `DueGenerationError(NO_PRIMARY_OWNER)` if none is flagged `is_primary_contact`."""
    if flat.occupancy_status == "tenant_occupied" and flat.current_tenant is not None:
        return "tenant", flat.current_tenant.id, flat.current_tenant.full_name
    if flat.primary_owner is None:
        raise DueGenerationError(flat_id=flat.id, reason="NO_PRIMARY_OWNER")
    return "owner", flat.primary_owner.id, flat.primary_owner.full_name


async def create_cycle_row(
    db: AsyncSession,
    *,
    tower_id: UUID,
    month: int,
    year: int,
    due_date: date,
    created_by_id: UUID,
) -> BillingCycle:
    """Snapshots the formula/grace-period version in effect *today* (cycle creation date, not
    the due date — overview.md edge case 14) and enforces the `(tower_id, month, year)`
    idempotency guarantee, first via a pre-check (fast, friendly 409) and then via the DB
    constraint itself (belt-and-braces against a concurrent duplicate request)."""
    as_of = date.today()

    formula = await get_current_formula(db, tower_id, as_of)
    if formula is None:
        raise AppError(
            404,
            "NO_FORMULA_CONFIGURED",
            "This tower has not configured a maintenance formula yet.",
        )
    grace = await get_current_grace_period(db, tower_id, as_of)
    grace_period_days = grace.grace_period_days if grace is not None else 0

    existing = await db.scalar(
        select(BillingCycle).where(
            BillingCycle.tower_id == tower_id,
            BillingCycle.month == month,
            BillingCycle.year == year,
        )
    )
    if existing is not None:
        raise AppError(
            409,
            "BILLING_CYCLE_ALREADY_EXISTS",
            "A billing cycle already exists for this tower/month/year.",
        )

    cycle = BillingCycle(
        tower_id=tower_id,
        month=month,
        year=year,
        due_date=due_date,
        formula_id=formula.id,
        grace_period_days_snapshot=grace_period_days,
        status="generating",
        created_by=created_by_id,
    )
    db.add(cycle)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise AppError(
            409,
            "BILLING_CYCLE_ALREADY_EXISTS",
            "A billing cycle already exists for this tower/month/year.",
        ) from exc
    return cycle


async def _generate_dues_for_cycle(
    db: AsyncSession, *, cycle: BillingCycle, formula: MaintenanceFormula
) -> list[GenerationFailure]:
    """Creates one `maintenance_dues` row per active flat. Per-flat failures (no active
    tenant *and* no primary owner) are collected and returned rather than raised, so one bad
    flat never aborts the rest of the cycle (overview.md edge case 12)."""
    failures: list[GenerationFailure] = []
    flat_ids = await flats_service.list_active_flat_ids(db, cycle.tower_id)

    for flat_id in flat_ids:
        flat = await flats_service.get_flat_read_model(db, flat_id)
        if flat is None:
            continue

        try:
            assigned_to_type, assigned_to_id, assigned_to_name = await assign_due(flat)
        except DueGenerationError as exc:
            failures.append(GenerationFailure(flat_id=str(exc.flat_id), reason=exc.reason))
            continue

        # `primary_owner_id_snapshot` must always be set (backend.md §5: "always captured
        # regardless of `assigned_to_type`, used for receipts"), including when the tenant
        # branch above was taken. `assign_due()` itself only validates primary-owner
        # existence on the owner/vacant branch (matching its spec verbatim), so re-check it
        # here for the tenant branch to uphold the column's NOT NULL contract — a
        # tenant-occupied flat with no primary owner flagged is just as much a Module 2
        # data-integrity gap as an owner-occupied one, and must fail the same way.
        if flat.primary_owner is None:
            failures.append(GenerationFailure(flat_id=str(flat.id), reason="NO_PRIMARY_OWNER"))
            continue

        amount = calculate_monthly_maintenance(
            formula.base_amount, formula.per_sqft_rate, flat.carpet_area
        )
        due = MaintenanceDue(
            billing_cycle_id=cycle.id,
            tower_id=cycle.tower_id,
            flat_id=flat.id,
            amount=amount,
            carpet_area_snapshot=flat.carpet_area,
            assigned_to_type=assigned_to_type,
            assigned_to_id=assigned_to_id,
            assigned_to_name_snapshot=assigned_to_name,
            primary_owner_id_snapshot=flat.primary_owner.id,
            due_date=cycle.due_date,
        )
        db.add(due)

    await db.flush()
    return failures


async def generate_dues_sync(
    db: AsyncSession, *, cycle: BillingCycle
) -> list[GenerationFailure]:
    """Sync path (<=300 active flats, backend.md §4): generates dues in the same
    request/transaction and flips the cycle to `active`."""
    formula = await db.get(MaintenanceFormula, cycle.formula_id)
    assert formula is not None, f"formula {cycle.formula_id} must exist (FK-enforced)"
    failures = await _generate_dues_for_cycle(db, cycle=cycle, formula=formula)
    cycle.status = "active"
    return failures


async def process_billing_cycle_job(db: AsyncSession, *, job: Job) -> list[GenerationFailure]:
    """Async/worker path (backend.md §4): consumed off `billing-cycle-jobs` by the ECS worker
    in production; in this sandbox (no SQS consumer running) this is the function a test or a
    manual `python -m app.worker.billing_cycle_worker` invocation calls to simulate "the
    worker picked up the message". Idempotent: a retried/duplicate delivery for a cycle that's
    already `active` is a safe no-op (backend.md §4)."""
    assert job.payload is not None, "billing_cycle jobs always carry a payload"
    cycle_id = UUID(job.payload["cycle_id"])
    cycle = await db.get(BillingCycle, cycle_id)
    if cycle is None:
        jobs_service.mark_failed(job, error_message=f"billing_cycle {cycle_id} not found")
        await db.commit()
        return []

    if cycle.status == "active":
        # Already generated by a prior delivery of this message — safe no-op.
        jobs_service.mark_done(job, result={"dues_created": 0, "already_active": True})
        await db.commit()
        return []

    jobs_service.mark_running(job)
    await db.flush()

    formula = await db.get(MaintenanceFormula, cycle.formula_id)
    assert formula is not None, f"formula {cycle.formula_id} must exist (FK-enforced)"
    failures = await _generate_dues_for_cycle(db, cycle=cycle, formula=formula)
    cycle.status = "active"

    dues_created = await db.scalar(
        select(func.count())
        .select_from(MaintenanceDue)
        .where(MaintenanceDue.billing_cycle_id == cycle.id)
    )
    jobs_service.mark_done(
        job, result={"dues_created": dues_created or 0, "failures": [f.__dict__ for f in failures]}
    )
    await db.commit()
    return failures
