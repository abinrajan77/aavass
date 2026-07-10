from typing import Literal, cast
from uuid import UUID

from pydantic import BaseModel

from app.models.job import Job

JobStatus = Literal["pending", "running", "done", "failed"]


class JobOut(BaseModel):
    job_id: UUID
    job_type: str
    status: JobStatus
    result: dict | None = None
    error_message: str | None = None

    @classmethod
    def from_model(cls, job: Job) -> "JobOut":
        # `job.status` is a plain `str` column (see app/models/job.py) whose values are
        # constrained to `JobStatus` only by application-level invariants (write paths in
        # app.services.jobs), not a DB-level enum/check constraint — cast, don't re-litigate
        # that contract with a runtime branch here.
        return cls(
            job_id=job.id,
            job_type=job.job_type,
            status=cast(JobStatus, job.status),
            result=job.result,
            error_message=job.error_message,
        )
