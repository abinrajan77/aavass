"""Shared canonical job-status polling route (`06-cloud-devops.md` §4) — one route for every
module's async jobs. `job_type` in the response distinguishes `billing_cycle`,
`special_collection`, `report_export`, etc."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission
from app.core.errors import AppError
from app.db.session import get_db
from app.models.job import Job
from app.schemas.job import JobOut

router = APIRouter(prefix="/towers/{tower_id}/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobOut)
async def get_job(
    tower_id: UUID,
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("VIEW_TOWER_DATA")),
) -> JobOut:
    job = await db.get(Job, job_id)
    if job is None or job.tower_id != tower_id:
        raise AppError(404, "JOB_NOT_FOUND", "Job not found.")
    return JobOut.from_model(job)
