"""5 fixed reports — backend.md §2. All guarded by `require_permission("VIEW_REPORTS")`
(admin-only in v1.0; flat owners use the separate owner-portal endpoints in `owner_portal.py`).
Every endpoint accepts `format` (`pdf`|`csv`, optional) — omitting it returns the JSON preview
used by the frontend's report table before export (backend.md §2, verbatim)."""

from datetime import UTC, date, datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_permission
from app.core.errors import AppError
from app.db.session import get_db
from app.models.billing_cycle import BillingCycle
from app.models.user import User
from app.services import export as export_service
from app.services import reporting, sqs

router = APIRouter(prefix="/towers/{tower_id}/reports", tags=["reports"])

ExportFormat = Literal["pdf", "csv"]


async def _handle_export(
    db: AsyncSession,
    *,
    tower_id: UUID,
    report_type: export_service.ReportType,
    format: ExportFormat,
    params: dict[str, Any],
    current_user: User,
) -> Response:
    """Shared sync/async branch for all 5 reports (backend.md §2.6): estimates row count first
    (cheap COUNT query, never materializes the full row list before deciding), renders
    synchronously for <=5000 rows, else enqueues an `export_jobs`/`jobs` pair and returns `202`.
    """
    row_count = await export_service.estimate_row_count(
        db, tower_id=tower_id, report_type=report_type, params=params
    )

    if row_count <= export_service.SYNC_EXPORT_ROW_THRESHOLD:
        table = await export_service.build_report_table(
            db, tower_id=tower_id, report_type=report_type, params=params
        )
        file_bytes, content_type = export_service.render_export_file(table, format=format)
        filename = f"{report_type}.{format}"
        return Response(
            content=file_bytes,
            media_type=content_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    job, _export_job, created = await export_service.get_or_create_export_job(
        db,
        tower_id=tower_id,
        report_type=report_type,
        format=format,
        params=params,
        requested_by=current_user.id,
    )
    await db.commit()

    if created:
        await sqs.enqueue(
            queue_name="report-export-jobs",
            payload={
                "job_id": str(job.id), "tower_id": str(tower_id), "report_type": report_type,
                "format": format, "params": params,
            },
            idempotency_key=export_service.export_job_idempotency_key(
                tower_id=tower_id, report_type=report_type, format=format, params=params
            ),
        )

    return JSONResponse(status_code=202, content={"job_id": str(job.id)})


@router.get("/collection")
async def get_collection_report(
    tower_id: UUID,
    billing_cycle_id: UUID = Query(...),
    format: ExportFormat | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("VIEW_REPORTS")),
) -> Response:
    cycle = await db.get(BillingCycle, billing_cycle_id)
    if cycle is None or cycle.tower_id != tower_id:
        raise AppError(404, "BILLING_CYCLE_NOT_FOUND", "Billing cycle not found.")

    if format is None:
        report = await reporting.build_collection_report(
            db, tower_id=tower_id, billing_cycle_id=billing_cycle_id
        )
        return JSONResponse(content=report.model_dump(mode="json"))

    return await _handle_export(
        db,
        tower_id=tower_id,
        report_type="collection",
        format=format,
        params={"billing_cycle_id": str(billing_cycle_id)},
        current_user=current_user,
    )


@router.get("/outstanding-dues")
async def get_outstanding_dues_report(
    tower_id: UUID,
    as_of_date: date | None = Query(default=None),
    format: ExportFormat | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("VIEW_REPORTS")),
) -> Response:
    resolved_as_of = as_of_date or datetime.now(UTC).date()

    if format is None:
        report = await reporting.build_outstanding_dues_report(
            db, tower_id=tower_id, as_of_date=resolved_as_of
        )
        return JSONResponse(content=report.model_dump(mode="json"))

    return await _handle_export(
        db,
        tower_id=tower_id,
        report_type="outstanding_dues",
        format=format,
        params={"as_of_date": resolved_as_of.isoformat()},
        current_user=current_user,
    )


@router.get("/expenditure")
async def get_expenditure_report(
    tower_id: UUID,
    period_start: date = Query(...),
    period_end: date = Query(...),
    format: ExportFormat | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("VIEW_REPORTS")),
) -> Response:
    if period_end < period_start:
        raise AppError(
            422,
            "VALIDATION_ERROR",
            "period_end must not be before period_start.",
            field_errors={"period_end": "must not be before period_start"},
        )

    if format is None:
        report = await reporting.build_expenditure_report(
            db, tower_id=tower_id, period_start=period_start, period_end=period_end
        )
        return JSONResponse(content=report.model_dump(mode="json"))

    return await _handle_export(
        db,
        tower_id=tower_id,
        report_type="expenditure",
        format=format,
        params={"period_start": period_start.isoformat(), "period_end": period_end.isoformat()},
        current_user=current_user,
    )


@router.get("/collection-vs-expenditure")
async def get_collection_vs_expenditure_report(
    tower_id: UUID,
    period_type: Literal["month", "financial_year"] = Query(...),
    month: int | None = Query(default=None, ge=1, le=12),
    year: int = Query(...),
    format: ExportFormat | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("VIEW_REPORTS")),
) -> Response:
    if period_type == "month" and month is None:
        raise AppError(
            422,
            "VALIDATION_ERROR",
            "month is required when period_type=month.",
            field_errors={"month": "required when period_type=month"},
        )

    if format is None:
        report = await reporting.build_collection_vs_expenditure_report(
            db, tower_id=tower_id, period_type=period_type, month=month, year=year
        )
        return JSONResponse(content=report.model_dump(mode="json"))

    params: dict[str, Any] = {"period_type": period_type, "year": year}
    if month is not None:
        params["month"] = month
    return await _handle_export(
        db,
        tower_id=tower_id,
        report_type="collection_vs_expenditure",
        format=format,
        params=params,
        current_user=current_user,
    )


@router.get("/tenant-register")
async def get_tenant_register_report(
    tower_id: UUID,
    format: ExportFormat | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("VIEW_REPORTS")),
) -> Response:
    if format is None:
        report = await reporting.build_tenant_register_report(db, tower_id=tower_id)
        return JSONResponse(content=report.model_dump(mode="json"))

    return await _handle_export(
        db,
        tower_id=tower_id,
        report_type="tenant_register",
        format=format,
        params={},
        current_user=current_user,
    )
