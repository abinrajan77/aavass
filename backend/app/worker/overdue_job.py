"""Nightly overdue-transition job entrypoint (backend.md §3: runs at 00:15 UTC daily, same ECS
worker service as the SQS-backed jobs). The job *body* (`is_overdue` / `run_overdue_transition`)
lives in `app.services.overdue` and is fully unit-testable on its own; this module is only the
`python -m app.worker.overdue_job` process a cron / ECS Scheduled Task invokes once a day.
"""

import asyncio

from app.db.session import AsyncSessionLocal
from app.services.overdue import run_overdue_transition


async def _main() -> None:
    async with AsyncSessionLocal() as db:
        flipped = await run_overdue_transition(db)
        print(f"overdue_job: flipped {len(flipped)} due(s) to overdue")


if __name__ == "__main__":
    asyncio.run(_main())
