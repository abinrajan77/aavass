"""Special-collection-due-generation worker (backend.md's `>300`-active-flats async path).

Mirrors `app.worker.billing_cycle_worker` exactly: in production this polls the
`special-collection-jobs` SQS queue and calls
`app.services.special_collection.process_special_collection_job` for each message.
`process_pending_jobs_once()` is the practical entrypoint for local dev and for tests that
want to simulate "the worker eventually picks the job up" — it scans for `pending`
`job_type='special_collection'` rows directly in the DB and processes them.
"""

import asyncio

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.job import Job
from app.services.special_collection import process_special_collection_job


async def process_pending_jobs_once() -> int:
    processed = 0
    async with AsyncSessionLocal() as db:
        pending_ids = (
            (
                await db.execute(
                    select(Job.id).where(
                        Job.job_type == "special_collection", Job.status == "pending"
                    )
                )
            )
            .scalars()
            .all()
        )
        for job_id in pending_ids:
            job = await db.get(Job, job_id)
            if job is None or job.status != "pending":
                continue
            await process_special_collection_job(db, job=job)
            processed += 1
    return processed


async def _main() -> None:
    processed = await process_pending_jobs_once()
    print(f"special_collection_worker: processed {processed} job(s)")


if __name__ == "__main__":
    asyncio.run(_main())
