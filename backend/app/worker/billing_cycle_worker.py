"""Billing-cycle-generation worker (backend.md §4 / `06-cloud-devops.md` §4).

In production this polls the `billing-cycle-jobs` SQS queue and calls
`app.services.billing_cycle.process_billing_cycle_job` for each message. Polling/ack/retry
wiring for a real SQS consumer is intentionally minimal here — this repo has no other SQS
consumer to mirror conventions from, and standing up `boto3.client("sqs").receive_message()`
long-polling plus visibility-timeout/delete-on-success handling is an infra concern for
whoever deploys the actual ECS worker service, not core Module 3 business logic (which lives
entirely in `process_billing_cycle_job` and is unit/integration-testable without any of this).

`process_pending_jobs_once()` is the practical entrypoint for local dev and for tests that
want to simulate "the worker eventually picks the job up": it scans for `pending`
`job_type='billing_cycle'` rows directly in the DB and processes them, without needing a real
SQS message in flight.
"""

import asyncio

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.job import Job
from app.services.billing_cycle import process_billing_cycle_job


async def process_pending_jobs_once() -> int:
    processed = 0
    async with AsyncSessionLocal() as db:
        pending_ids = (
            (
                await db.execute(
                    select(Job.id).where(Job.job_type == "billing_cycle", Job.status == "pending")
                )
            )
            .scalars()
            .all()
        )
        for job_id in pending_ids:
            job = await db.get(Job, job_id)
            if job is None or job.status != "pending":
                continue
            await process_billing_cycle_job(db, job=job)
            processed += 1
    return processed


async def _main() -> None:
    processed = await process_pending_jobs_once()
    print(f"billing_cycle_worker: processed {processed} job(s)")


if __name__ == "__main__":
    asyncio.run(_main())
