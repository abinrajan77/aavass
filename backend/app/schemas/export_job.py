"""Response schema for the `202 Accepted` export-job-enqueued branch — backend.md §2.6. The
job's actual status/result is polled via the shared `GET /api/v1/towers/{tower_id}/jobs/{job_id}`
route (`app.schemas.job.JobOut`), not a route of this module's own."""

from uuid import UUID

from pydantic import BaseModel


class ExportJobAccepted(BaseModel):
    job_id: UUID
