"""Generic async-job bookkeeping table, per `06-cloud-devops.md` §4: one shared table/route for
every module's async jobs (`job_type` discriminator: `billing_cycle`, `special_collection`,
`report_export`, ...). Module 3 is the first to populate it (billing-cycle generation beyond the
sync threshold); Modules 4/5 reuse the same table and the same
`GET /api/v1/towers/{tower_id}/jobs/{job_id}` route rather than inventing their own."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import TIMESTAMP, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base_class import Base


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    tower_id: Mapped[UUID] = mapped_column(ForeignKey("towers.id"), nullable=False, index=True)
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # 'pending' | 'running' | 'done' | 'failed'
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Natural key (e.g. "tower_id:month:year") so a retried/duplicate enqueue is a safe no-op.
    idempotency_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )
