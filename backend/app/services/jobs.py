"""Generic async-job bookkeeping (`app.models.job.Job`) — shared by every module's async paths
per `06-cloud-devops.md` §4. Only Module 3 (billing-cycle generation) populates it today;
Modules 4/5 reuse the same table/route for their own `job_type`s rather than inventing a
module-specific job-status path.
"""

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job


async def create_job(
    db: AsyncSession,
    *,
    tower_id: UUID,
    job_type: str,
    payload: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
) -> Job:
    job = Job(
        tower_id=tower_id,
        job_type=job_type,
        status="pending",
        payload=payload,
        idempotency_key=idempotency_key,
    )
    db.add(job)
    await db.flush()
    return job


def mark_running(job: Job) -> None:
    job.status = "running"


def mark_done(job: Job, *, result: dict[str, Any] | None = None) -> None:
    job.status = "done"
    job.result = result


def mark_failed(job: Job, *, error_message: str) -> None:
    job.status = "failed"
    job.error_message = error_message
