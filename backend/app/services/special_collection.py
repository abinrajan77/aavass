"""Special-collection business logic: equal-split due generation and collection rollups.

`compute_equal_split` (pure) and `generate_dues` (DB writes) are called by both the sync
(<=300 active flats) and async (`special-collection-jobs` SQS, `process_special_collection_job`
below) paths, so formula calc + allocation behave identically regardless of scale — mirrors
`app.services.billing_cycle`'s `_generate_dues_for_cycle`/`generate_dues_sync`/
`process_billing_cycle_job` split. Neither `compute_equal_split` nor `generate_dues` knows or
cares whether it's running inline in the request or inside a background job.

Also registers this module's `record_payment()` dispatch-table entries (backend.md §"Reuse of
Module 3 payment/receipt flow") at import time — `app/api/v1/special_collections.py` imports
this module, and that router is imported by `app/api/v1/__init__.py` at app startup, so the
registration below always runs before any request is handled.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.job import Job
from app.models.special_collection import SpecialCollection
from app.models.special_collection_due import SpecialCollectionDue
from app.services import jobs as jobs_service
from app.services.flat_directory import ActiveFlatRecord, FlatDirectory, RealFlatDirectory
from app.services.payments import (
    register_due_resolver,
    register_label_resolver,
    register_owner_name_resolver,
)

# backend.md: beyond this many active flats, generation moves to the `special-collection-jobs`
# async path (mirrors `app.services.billing_cycle.SYNC_GENERATION_FLAT_THRESHOLD`).
SYNC_DUE_GENERATION_FLAT_THRESHOLD = 300


async def _resolve_special_collection_due(
    db: AsyncSession, *, due_id: UUID, tower_id: UUID
) -> SpecialCollectionDue:
    due = await db.scalar(
        select(SpecialCollectionDue).where(
            SpecialCollectionDue.id == due_id, SpecialCollectionDue.tower_id == tower_id
        )
    )
    if due is None:
        raise AppError(404, "DUE_NOT_FOUND", "Special collection due not found.")
    return due


async def _special_collection_billing_period_label(
    db: AsyncSession, due: SpecialCollectionDue
) -> str:
    collection = await db.get(SpecialCollection, due.special_collection_id)
    assert collection is not None, (
        f"special_collection {due.special_collection_id} must exist (FK-enforced)"
    )
    # backend.md: "populated with 'Special Collection: {special_collection.title}' instead of
    # a maintenance billing-cycle label".
    return f"Special Collection: {collection.title}"


async def _special_collection_owner_name(db: AsyncSession, due: SpecialCollectionDue) -> str:
    # Already denormalized on the due row at generation time — no join needed.
    return due.owner_name


register_due_resolver("special_collection", _resolve_special_collection_due)
register_label_resolver("special_collection", _special_collection_billing_period_label)
register_owner_name_resolver("special_collection", _special_collection_owner_name)


@dataclass(frozen=True)
class DueAllocation:
    flat_id: UUID
    flat_number: str
    owner_id: UUID
    owner_name: str
    amount: Decimal


@dataclass(frozen=True)
class SkippedFlatInfo:
    flat_id: UUID
    flat_number: str
    reason: str = "NO_ACTIVE_OWNER"


def _natural_sort_key(flat_number: str) -> tuple:
    """Splits a flat number into alternating text/number chunks so "2" sorts before "10"
    (a plain string sort would put "10" before "2", which is not the deterministic,
    human-expected ordering backend.md's test plan item 2 relies on). Handles purely numeric
    flat numbers ("101") as well as alphanumeric ones ("A-101")."""
    return tuple(
        int(chunk) if chunk.isdigit() else chunk.lower()
        for chunk in re.split(r"(\d+)", flat_number)
        if chunk != ""
    )


def compute_equal_split(
    total_amount: Decimal, flats: Sequence[ActiveFlatRecord]
) -> tuple[list[DueAllocation], list[SkippedFlatInfo]]:
    """Implements backend.md's equal-split algorithm exactly:

    `total_paise = round(total_amount * 100)`; `n = count(eligible flats)`;
    `base_paise = total_paise // n`; `remainder = total_paise % n`; flats sorted by
    `flat_number` ascending; the first `remainder` flats (by that ordering) get
    `base_paise + 1`, the rest get `base_paise`; each due's `amount = paise / 100`.

    This guarantees `sum(due.amount for due in dues) == total_amount` exactly, with
    deterministic, reproducible distribution of odd cents (backend.md test plan item 2).

    Flats with no active owner (`owner_id is None`) are skipped, never fatal (test plan
    item 3) — pure function, no I/O, so it is unit-testable without a database.
    """
    skipped = [
        SkippedFlatInfo(flat_id=f.flat_id, flat_number=f.flat_number)
        for f in flats
        if f.owner_id is None
    ]
    eligible = sorted(
        (f for f in flats if f.owner_id is not None),
        key=lambda f: _natural_sort_key(f.flat_number),
    )

    if not eligible:
        return [], skipped

    total_paise = int((total_amount * 100).to_integral_value(rounding=ROUND_HALF_UP))
    n = len(eligible)
    base_paise, remainder = divmod(total_paise, n)

    allocations: list[DueAllocation] = []
    for index, flat in enumerate(eligible):
        paise = base_paise + 1 if index < remainder else base_paise
        assert flat.owner_id is not None
        assert flat.owner_name is not None
        allocations.append(
            DueAllocation(
                flat_id=flat.flat_id,
                flat_number=flat.flat_number,
                owner_id=flat.owner_id,
                owner_name=flat.owner_name,
                amount=(Decimal(paise) / 100).quantize(Decimal("0.01")),
            )
        )
    return allocations, skipped


async def generate_dues(
    db: AsyncSession,
    *,
    special_collection: SpecialCollection,
    flats: Sequence[ActiveFlatRecord],
) -> None:
    """Synchronous due-generation path (<=300 active flats today — see
    `SYNC_DUE_GENERATION_FLAT_THRESHOLD`). Creates one `SpecialCollectionDue` row per
    eligible flat, snapshots `skipped_flats` onto the collection, and stamps
    `dues_generated_at`. Caller commits (mirrors the audit-log atomicity contract: one
    transaction covers the collection row, its dues, and the audit log entry)."""
    allocations, skipped = compute_equal_split(special_collection.total_amount, flats)

    for allocation in allocations:
        db.add(
            SpecialCollectionDue(
                special_collection_id=special_collection.id,
                tower_id=special_collection.tower_id,
                flat_id=allocation.flat_id,
                flat_number=allocation.flat_number,
                owner_id=allocation.owner_id,
                owner_name=allocation.owner_name,
                amount=allocation.amount,
                due_date=special_collection.due_date,
                status="pending",
            )
        )

    special_collection.skipped_flats = [
        {"flat_id": str(s.flat_id), "flat_number": s.flat_number, "reason": s.reason}
        for s in skipped
    ]
    special_collection.dues_generated_at = datetime.now(UTC)
    await db.flush()


async def process_special_collection_job(
    db: AsyncSession, *, job: Job, flat_directory: FlatDirectory | None = None
) -> None:
    """Async/worker path (backend.md: ">300 active flats enqueues `special-collection-jobs`
    and returns 202"): consumed off that queue by the ECS worker in production; in this
    sandbox (no SQS consumer running) this is the function a test or a manual
    `python -m app.worker.special_collection_worker` invocation calls to simulate "the worker
    picked up the message". Idempotent: a retried/duplicate delivery for a collection whose
    dues are already generated is a safe no-op — mirrors
    `app.services.billing_cycle.process_billing_cycle_job`."""
    assert job.payload is not None, "special_collection jobs always carry a payload"
    collection_id = UUID(job.payload["special_collection_id"])
    collection = await db.get(SpecialCollection, collection_id)
    if collection is None:
        jobs_service.mark_failed(job, error_message=f"special_collection {collection_id} not found")
        await db.commit()
        return

    if collection.dues_generated_at is not None:
        # Already generated by a prior delivery of this message — safe no-op.
        jobs_service.mark_done(job, result={"dues_created": 0, "already_generated": True})
        await db.commit()
        return

    jobs_service.mark_running(job)
    await db.flush()

    directory = flat_directory or RealFlatDirectory(db=db)
    flats = await directory.list_active_flats(tower_id=collection.tower_id)
    await generate_dues(db, special_collection=collection, flats=flats)

    dues_created = await db.scalar(
        select(func.count())
        .select_from(SpecialCollectionDue)
        .where(SpecialCollectionDue.special_collection_id == collection.id)
    )
    jobs_service.mark_done(job, result={"dues_created": dues_created or 0})
    await db.commit()


async def rollups_for_collections(
    db: AsyncSession, *, collection_ids: Sequence[UUID]
) -> dict[UUID, dict]:
    """Single grouped query for pending/paid/overdue counts + collected amount across every
    collection id given — avoids N+1 per-collection status checks (cloud.md latency budget:
    "pre-aggregate via a single grouped query, not N+1 per-due status checks")."""
    result: dict[UUID, dict] = {
        cid: {
            "pending_count": 0,
            "paid_count": 0,
            "overdue_count": 0,
            "collected_amount": Decimal("0.00"),
        }
        for cid in collection_ids
    }
    if not collection_ids:
        return result

    rows = (
        await db.execute(
            select(
                SpecialCollectionDue.special_collection_id,
                SpecialCollectionDue.status,
                func.count().label("cnt"),
                func.coalesce(func.sum(SpecialCollectionDue.amount), 0).label("amt"),
            )
            .where(SpecialCollectionDue.special_collection_id.in_(collection_ids))
            .group_by(SpecialCollectionDue.special_collection_id, SpecialCollectionDue.status)
        )
    ).all()
    for collection_id, status, count, amount in rows:
        bucket = result[collection_id]
        if status == "pending":
            bucket["pending_count"] = count
        elif status == "paid":
            bucket["paid_count"] = count
            bucket["collected_amount"] = Decimal(amount)
        elif status == "overdue":
            bucket["overdue_count"] = count
    return result
