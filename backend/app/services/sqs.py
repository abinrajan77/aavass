"""Thin SQS enqueue wrapper for the `billing-cycle-jobs` queue (`06-cloud-devops.md` §4).

`boto3` is lazy-imported *inside* `enqueue()`, only reached when `settings.sqs_queue_url` is
configured, so local/dev/test runs — where no real queue is configured — never need `boto3`
installed or reachable. The `jobs` row (`app.services.jobs.create_job`) created in the same DB
transaction as this call is the actual source of truth the client polls
(`GET /api/v1/towers/{tower_id}/jobs/{job_id}`); this function only affects whether a real SQS
worker gets a message to pick the job up out-of-band — its absence in dev doesn't break the
202-Accepted contract, it just means nothing will asynchronously advance the job's status
unless something else (a worker process, or a test calling
`app.services.billing_cycle.process_billing_cycle_job` directly) does the work.

Idempotency of the *queue message itself* is a courtesy, not the safety net — the real
idempotency guard is the `UNIQUE(tower_id, month, year)` constraint on `billing_cycles` plus
the `UNIQUE(billing_cycle_id, flat_id)` constraint on `maintenance_dues` (backend.md §4).
"""

from __future__ import annotations

import json
from typing import Any

from app.core.config import get_settings

settings = get_settings()


async def enqueue(*, queue_name: str, payload: dict[str, Any], idempotency_key: str) -> None:
    if not settings.sqs_queue_url:
        return

    import boto3  # lazy: only required when a real queue is configured

    client = boto3.client("sqs", region_name=settings.aws_region)
    client.send_message(
        QueueUrl=settings.sqs_queue_url,
        MessageBody=json.dumps(payload),
        MessageAttributes={
            "idempotency_key": {"DataType": "String", "StringValue": idempotency_key},
            "queue_name": {"DataType": "String", "StringValue": queue_name},
        },
    )
