"""Async export-job tracking for large (>5000 row) report exports (backend.md §1, cloud.md
"Async report exports"). `params` is the natural key for idempotency: a retried/duplicate
export request with identical `(tower_id, report_type, format, params)` while a prior job is
still `pending`/`running` is a safe no-op — see `app.services.export.get_or_create_export_job`.

This module's `id` deliberately doubles as the shared `jobs.id` row created alongside it (see
that service function's docstring for the reconciliation rationale) so the frontend polls the
one canonical `GET /api/v1/towers/{tower_id}/jobs/{job_id}` route regardless of job type."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import TIMESTAMP, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base_class import Base


class ExportJob(Base):
    __tablename__ = "export_jobs"

    # No server_default: the router mints this id explicitly so it can equal the paired
    # `jobs.id` row (see module docstring) — never left to `gen_random_uuid()` here.
    id: Mapped[UUID] = mapped_column(primary_key=True)
    tower_id: Mapped[UUID] = mapped_column(ForeignKey("towers.id"), nullable=False, index=True)
    # 'collection' | 'outstanding_dues' | 'expenditure' | 'collection_vs_expenditure' |
    # 'tenant_register'
    report_type: Mapped[str] = mapped_column(String(40), nullable=False)
    # 'pdf' | 'csv'
    format: Mapped[str] = mapped_column(String(10), nullable=False)
    # period/date-range/billing_cycle_id etc. — the natural key for idempotency.
    params: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # 'pending' | 'running' | 'done' | 'failed'
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_s3_key: Mapped[str | None] = mapped_column(String(300), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    requested_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_export_jobs_tower_status", "tower_id", "status"),
    )
