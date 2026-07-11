"""Shared export flow for all 5 report endpoints — backend.md §2.6, cloud.md "Async report
exports".

**`export_jobs` vs. the shared `jobs` table — reconciliation decision**: `export_jobs` is the
natural-key idempotency source of truth (`(tower_id, report_type, format, params)` + status),
exactly as backend.md's test plan describes. The shared `jobs` table (`app.models.job.Job`) is
what the existing canonical `GET /api/v1/towers/{tower_id}/jobs/{job_id}` route reads from
(`app/api/v1/jobs.py`) — this module does not get its own job-status route. Rather than writing
two independently-keyed rows that could drift out of lockstep, `get_or_create_export_job()`
mints a `Job` row first and then creates the `ExportJob` row with `id = job.id` — the same
primary key serves both tables, so "keep them in sync" is structural (one id, looked up via two
different tables' own columns) rather than something every status-transition call site has to
remember to do twice. `mark_report_export_running/done/failed` below always update both rows in
the same call.
"""

import csv
import io
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.export_job import ExportJob
from app.models.job import Job
from app.services import reporting, storage
from app.services.pdf import render_tabular_report_pdf

ReportType = Literal[
    "collection", "outstanding_dues", "expenditure", "collection_vs_expenditure", "tenant_register"
]
ExportFormat = Literal["pdf", "csv"]

SYNC_EXPORT_ROW_THRESHOLD = 5000


@dataclass(frozen=True)
class ReportTable:
    title: str
    headers: list[str]
    rows: list[list[str]]
    summary_lines: list[str]


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value)


async def estimate_row_count(
    db: AsyncSession, *, tower_id: UUID, report_type: ReportType, params: dict[str, Any]
) -> int:
    """Cheap COUNT-only query per report type — decides sync-vs-async *before* any full row
    list is built (backend.md §2.6: "backend estimates row count ... before rendering")."""
    if report_type == "collection":
        return await reporting.count_collection_rows(
            db, tower_id=tower_id, billing_cycle_id=UUID(params["billing_cycle_id"])
        )
    if report_type == "outstanding_dues":
        return await reporting.count_outstanding_dues_rows(db, tower_id=tower_id)
    if report_type == "expenditure":
        return await reporting.count_expenditure_rows(
            db,
            tower_id=tower_id,
            period_start=datetime.fromisoformat(params["period_start"]).date(),
            period_end=datetime.fromisoformat(params["period_end"]).date(),
        )
    if report_type == "collection_vs_expenditure":
        period_start, period_end, _ = reporting.resolve_period(
            period_type=params["period_type"], month=params.get("month"), year=params["year"]
        )
        return await reporting.count_collection_vs_expenditure_rows(
            db, tower_id=tower_id, period_start=period_start, period_end=period_end
        )
    if report_type == "tenant_register":
        return await reporting.count_tenant_register_rows(db, tower_id=tower_id)
    raise AppError(422, "INVALID_REPORT_TYPE", f"Unknown report type: {report_type}")


async def build_report_table(
    db: AsyncSession, *, tower_id: UUID, report_type: ReportType, params: dict[str, Any]
) -> ReportTable:
    """Builds the headers/rows/summary used by both CSV and PDF renderers — CSV headers and PDF
    table headers are the exact same `headers` list, so the two are column-identical by
    construction (backend.md test-plan requirement)."""
    if report_type == "collection":
        collection_report = await reporting.build_collection_report(
            db, tower_id=tower_id, billing_cycle_id=UUID(params["billing_cycle_id"])
        )
        headers = [
            "flat_number", "owner_names", "resident_type", "resident_name", "amount_due",
            "status", "payment_date", "payment_mode", "reference_number", "receipt_number",
        ]
        rows = [
            [
                _fmt(r.flat_number), _fmt(r.owner_names), _fmt(r.resident_type),
                _fmt(r.resident_name), _fmt(r.amount_due), _fmt(r.status), _fmt(r.payment_date),
                _fmt(r.payment_mode), _fmt(r.reference_number), _fmt(r.receipt_number),
            ]
            for r in collection_report.items
        ]
        summary = [f"{k}: {_fmt(v)}" for k, v in collection_report.totals.items()]
        return ReportTable(
            title=(
                f"Monthly Collection Report — "
                f"{collection_report.billing_month}/{collection_report.billing_year}"
            ),
            headers=headers, rows=rows, summary_lines=summary,
        )

    if report_type == "outstanding_dues":
        as_of = (
            datetime.fromisoformat(params["as_of_date"]).date()
            if params.get("as_of_date")
            else datetime.now(UTC).date()
        )
        outstanding_report = await reporting.build_outstanding_dues_report(
            db, tower_id=tower_id, as_of_date=as_of
        )
        headers = [
            "flat_number", "due_type", "owner_names", "resident_name", "amount_due", "due_date",
            "grace_period_days", "days_overdue",
        ]
        rows = [
            [
                _fmt(r.flat_number), _fmt(r.due_type), _fmt(r.owner_names), _fmt(r.resident_name),
                _fmt(r.amount_due), _fmt(r.due_date), _fmt(r.grace_period_days),
                _fmt(r.days_overdue),
            ]
            for r in outstanding_report.items
        ]
        summary = [f"total_outstanding: {_fmt(outstanding_report.total_outstanding)}"]
        return ReportTable(
            title=f"Outstanding Dues Report — as of {outstanding_report.as_of_date.isoformat()}",
            headers=headers, rows=rows, summary_lines=summary,
        )

    if report_type == "expenditure":
        expenditure_report = await reporting.build_expenditure_report(
            db,
            tower_id=tower_id,
            period_start=datetime.fromisoformat(params["period_start"]).date(),
            period_end=datetime.fromisoformat(params["period_end"]).date(),
        )
        headers = ["date", "category", "description", "vendor_payee", "amount", "payment_mode",
                   "has_attachment"]
        rows = [
            [
                _fmt(r.date), _fmt(r.category), _fmt(r.description), _fmt(r.vendor_payee),
                _fmt(r.amount), _fmt(r.payment_mode), _fmt(r.has_attachment),
            ]
            for r in expenditure_report.items
        ]
        summary = [f"{c.category}: {_fmt(c.total)}" for c in expenditure_report.category_totals]
        summary.append(f"grand_total: {_fmt(expenditure_report.grand_total)}")
        return ReportTable(
            title=f"Expenditure Report — {expenditure_report.period_start.isoformat()} to "
                  f"{expenditure_report.period_end.isoformat()}",
            headers=headers, rows=rows, summary_lines=summary,
        )

    if report_type == "collection_vs_expenditure":
        cve_report = await reporting.build_collection_vs_expenditure_report(
            db,
            tower_id=tower_id,
            period_type=params["period_type"],
            month=params.get("month"),
            year=params["year"],
        )
        headers = ["category", "total"]
        rows = [[_fmt(c.category), _fmt(c.total)] for c in cve_report.expenditure_by_category]
        summary = [
            f"maintenance_collected: {_fmt(cve_report.maintenance_collected)}",
            f"special_collection_collected: {_fmt(cve_report.special_collection_collected)}",
            f"total_collected: {_fmt(cve_report.total_collected)}",
            f"total_expenditure: {_fmt(cve_report.total_expenditure)}",
            f"net: {_fmt(cve_report.net)}",
        ]
        return ReportTable(
            title=f"Collection vs Expenditure Summary — {cve_report.period_label}",
            headers=headers, rows=rows, summary_lines=summary,
        )

    if report_type == "tenant_register":
        tenant_report = await reporting.build_tenant_register_report(db, tower_id=tower_id)
        headers = ["flat_number", "tenant_name", "phone_number", "email", "lease_start",
                   "lease_end", "is_current"]
        rows = [
            [
                _fmt(r.flat_number), _fmt(r.tenant_name), _fmt(r.phone_number), _fmt(r.email),
                _fmt(r.lease_start), _fmt(r.lease_end), _fmt(r.is_current),
            ]
            for r in tenant_report.items
        ]
        return ReportTable(
            title="Tenant Register", headers=headers, rows=rows, summary_lines=[]
        )

    raise AppError(422, "INVALID_REPORT_TYPE", f"Unknown report type: {report_type}")


def render_export_file(table: ReportTable, *, format: ExportFormat) -> tuple[bytes, str]:
    if format == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(table.headers)
        writer.writerows(table.rows)
        if table.summary_lines:
            writer.writerow([])
            for line in table.summary_lines:
                writer.writerow([line])
        return buf.getvalue().encode("utf-8"), "text/csv"

    pdf_bytes = render_tabular_report_pdf(
        title=table.title, headers=table.headers, rows=table.rows,
        summary_lines=table.summary_lines,
    )
    return pdf_bytes, "application/pdf"


async def get_or_create_export_job(
    db: AsyncSession,
    *,
    tower_id: UUID,
    report_type: ReportType,
    format: ExportFormat,
    params: dict[str, Any],
    requested_by: UUID,
) -> tuple[Job, ExportJob, bool]:
    """Idempotency check against `export_jobs`'s natural key
    `(tower_id, report_type, format, params)` — a duplicate/retried request while a matching job
    is still `pending`/`running` returns the existing pair rather than enqueuing a second SQS
    message (backend.md test plan). Returns `(job, export_job, created)`."""
    existing = await db.scalar(
        select(ExportJob).where(
            ExportJob.tower_id == tower_id,
            ExportJob.report_type == report_type,
            ExportJob.format == format,
            ExportJob.params == params,
            ExportJob.status.in_(["pending", "running"]),
        )
    )
    if existing is not None:
        job = await db.get(Job, existing.id)
        assert job is not None, f"jobs row {existing.id} must exist alongside export_jobs row"
        return job, existing, False

    job = Job(
        tower_id=tower_id,
        job_type="report_export",
        status="pending",
        payload={
            "tower_id": str(tower_id), "report_type": report_type, "format": format,
            "params": params,
        },
        idempotency_key=export_job_idempotency_key(
            tower_id=tower_id, report_type=report_type, format=format, params=params
        ),
    )
    db.add(job)
    await db.flush()

    export_job = ExportJob(
        id=job.id,
        tower_id=tower_id,
        report_type=report_type,
        format=format,
        params=params,
        status="pending",
        requested_by=requested_by,
    )
    db.add(export_job)
    await db.flush()
    return job, export_job, True


async def process_report_export_job(db: AsyncSession, *, job: Job) -> None:
    """Worker-equivalent (backend.md §2.6 / cloud.md "worker responsibility") — in this sandbox
    (no real SQS consumer) this is called directly by a test/manual trigger simulating "the
    worker picked up the message", mirroring
    `app.services.billing_cycle.process_billing_cycle_job`."""
    export_job = await db.get(ExportJob, job.id)
    if export_job is None:
        job.status = "failed"
        job.error_message = f"export_jobs row {job.id} not found"
        await db.commit()
        return

    if export_job.status == "done":
        # Already processed by a prior delivery of this message — safe no-op.
        return

    job.status = "running"
    export_job.status = "running"
    await db.flush()

    try:
        table = await build_report_table(
            db,
            tower_id=export_job.tower_id,
            report_type=export_job.report_type,  # type: ignore[arg-type]
            params=export_job.params,
        )
        file_bytes, _content_type = render_export_file(
            table, format=export_job.format  # type: ignore[arg-type]
        )
        s3_key = f"report-exports/{export_job.tower_id}/{export_job.id}.{export_job.format}"
        await storage.upload_bytes(
            key=s3_key,
            data=file_bytes,
            content_type="text/csv" if export_job.format == "csv" else "application/pdf",
        )
        download_url = await storage.presigned_get_url(key=s3_key)

        export_job.status = "done"
        export_job.file_s3_key = s3_key
        export_job.row_count = len(table.rows)
        export_job.completed_at = datetime.now(UTC)

        job.status = "done"
        job.result = {"download_url": download_url}
    except Exception as exc:  # pragma: no cover - defensive worker-failure path
        export_job.status = "failed"
        export_job.error_message = str(exc)
        job.status = "failed"
        job.error_message = str(exc)

    await db.commit()


def export_job_idempotency_key(
    *, tower_id: UUID, report_type: str, format: str, params: dict[str, Any]
) -> str:
    """Deterministic natural key covering the full `(tower_id, report_type, format, params)`
    tuple — a retried enqueue for the identical filter combination (e.g. the same
    `billing_cycle_id`) must resolve to the same key so a real SQS consumer's own dedup would
    also treat it as a duplicate; `params` is included via a stable (sorted-keys) JSON dump
    since two different filter combinations (e.g. different billing cycles) must never collide."""
    stable_params = json.dumps(params, sort_keys=True, separators=(",", ":"))
    return f"{tower_id}:{report_type}:{format}:{stable_params}"
