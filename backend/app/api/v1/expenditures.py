from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_user,
    require_permission,
    require_permission_with_member_id,
)
from app.core.errors import AppError
from app.core.pagination import Pagination, pagination_params
from app.db.session import get_db
from app.models.association_member import AssociationMember
from app.models.expenditure import Expenditure
from app.models.user import User
from app.schemas.common import PageEnvelope
from app.schemas.expenditure import (
    AttachmentUploadUrlRequest,
    AttachmentUploadUrlResponse,
    AttachmentUrlResponse,
    ComplexContributionCreate,
    ExpenditureCreate,
    ExpenditureOut,
    ExpenditureUpdate,
)
from app.services.audit import write_audit_log
from app.services.storage import (
    ALLOWED_ATTACHMENT_CONTENT_TYPES,
    MAX_ATTACHMENT_BYTES,
    build_expenditure_attachment_key,
    generate_attachment_put_url,
    generate_get_url,
)

router = APIRouter(prefix="/towers/{tower_id}/expenditures", tags=["expenditures"])


def _snapshot(expenditure: Expenditure) -> dict:
    return {
        "expenditure_date": expenditure.expenditure_date.isoformat(),
        "category": expenditure.category,
        "description": expenditure.description,
        "vendor_payee_name": expenditure.vendor_payee_name,
        "amount": str(expenditure.amount),
        "payment_mode": expenditure.payment_mode,
        "attachment_s3_key": expenditure.attachment_s3_key,
        "is_complex_contribution": expenditure.is_complex_contribution,
        "complex_total_amount": (
            str(expenditure.complex_total_amount)
            if expenditure.complex_total_amount is not None
            else None
        ),
    }


@router.post("", response_model=ExpenditureOut, status_code=201)
async def create_expenditure(
    tower_id: UUID,
    payload: ExpenditureCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    member: AssociationMember = Depends(require_permission_with_member_id("MANAGE_EXPENDITURE")),
) -> ExpenditureOut:
    expenditure = Expenditure(
        tower_id=tower_id,
        expenditure_date=payload.expenditure_date,
        category=payload.category.value,
        description=payload.description,
        vendor_payee_name=payload.vendor_payee_name,
        amount=payload.amount,
        payment_mode=payload.payment_mode,
        attachment_s3_key=payload.attachment_s3_key,
        is_complex_contribution=False,
        complex_total_amount=None,
        recorded_by=member.id,
    )
    db.add(expenditure)
    await db.flush()

    await write_audit_log(
        db,
        actor=current_user,
        tower_id=tower_id,
        action="EXPENDITURE_CREATED",
        entity_type="Expenditure",
        entity_id=expenditure.id,
        before=None,
        after=_snapshot(expenditure),
    )
    await db.commit()
    await db.refresh(expenditure)
    return ExpenditureOut.model_validate(expenditure)


@router.post("/complex-contribution", response_model=ExpenditureOut, status_code=201)
async def create_complex_contribution_expenditure(
    tower_id: UUID,
    payload: ComplexContributionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    member: AssociationMember = Depends(require_permission_with_member_id("MANAGE_EXPENDITURE")),
) -> ExpenditureOut:
    expenditure = Expenditure(
        tower_id=tower_id,
        expenditure_date=payload.expenditure_date,
        category=payload.category.value,
        description=payload.description,
        vendor_payee_name=payload.vendor_payee_name,
        amount=payload.amount,
        payment_mode=payload.payment_mode,
        attachment_s3_key=payload.attachment_s3_key,
        is_complex_contribution=True,
        complex_total_amount=payload.complex_total_amount,
        recorded_by=member.id,
    )
    db.add(expenditure)
    await db.flush()

    await write_audit_log(
        db,
        actor=current_user,
        tower_id=tower_id,
        action="EXPENDITURE_CREATED",
        entity_type="Expenditure",
        entity_id=expenditure.id,
        before=None,
        after=_snapshot(expenditure),
    )
    await db.commit()
    await db.refresh(expenditure)
    return ExpenditureOut.model_validate(expenditure)


@router.get("", response_model=PageEnvelope[ExpenditureOut])
async def list_expenditures(
    tower_id: UUID,
    category: str | None = None,
    is_complex_contribution: bool | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    pagination: Pagination = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("VIEW_TOWER_DATA")),
) -> PageEnvelope[ExpenditureOut]:
    filters = [Expenditure.tower_id == tower_id]
    if category is not None:
        filters.append(Expenditure.category == category)
    if is_complex_contribution is not None:
        filters.append(Expenditure.is_complex_contribution == is_complex_contribution)
    if date_from is not None:
        filters.append(Expenditure.expenditure_date >= date_from)
    if date_to is not None:
        filters.append(Expenditure.expenditure_date <= date_to)

    total = await db.scalar(select(func.count()).select_from(Expenditure).where(*filters))
    rows = (
        (
            await db.execute(
                select(Expenditure)
                .where(*filters)
                .order_by(Expenditure.expenditure_date.desc(), Expenditure.created_at.desc())
                .offset(pagination.offset)
                .limit(pagination.page_size)
            )
        )
        .scalars()
        .all()
    )
    return PageEnvelope(
        items=[ExpenditureOut.model_validate(r) for r in rows],
        page=pagination.page,
        page_size=pagination.page_size,
        total=total or 0,
    )


@router.post(
    "/attachment-upload-url", response_model=AttachmentUploadUrlResponse, status_code=201
)
async def create_attachment_upload_url(
    tower_id: UUID,
    payload: AttachmentUploadUrlRequest,
    _member=Depends(require_permission("MANAGE_EXPENDITURE")),
) -> AttachmentUploadUrlResponse:
    if payload.content_type not in ALLOWED_ATTACHMENT_CONTENT_TYPES:
        raise AppError(
            422,
            "UNSUPPORTED_CONTENT_TYPE",
            "Attachment must be a PDF, JPEG, or PNG file.",
            field_errors={
                "content_type": "must be one of application/pdf, image/jpeg, image/png"
            },
        )
    if payload.content_length is not None and payload.content_length > MAX_ATTACHMENT_BYTES:
        raise AppError(
            413,
            "ATTACHMENT_TOO_LARGE",
            "Attachment exceeds the 10 MB size limit.",
            field_errors={"content_length": "must not exceed 10485760 bytes"},
        )

    attachment_id = uuid4()
    s3_key = build_expenditure_attachment_key(
        tower_id=tower_id, attachment_id=attachment_id, filename=payload.filename
    )
    upload_url = generate_attachment_put_url(s3_key=s3_key, content_type=payload.content_type)
    return AttachmentUploadUrlResponse(
        upload_url=upload_url,
        attachment_s3_key=s3_key,
        max_content_length=MAX_ATTACHMENT_BYTES,
    )


@router.get("/{expenditure_id}", response_model=ExpenditureOut)
async def get_expenditure(
    tower_id: UUID,
    expenditure_id: UUID,
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("VIEW_TOWER_DATA")),
) -> ExpenditureOut:
    expenditure = await db.scalar(
        select(Expenditure).where(
            Expenditure.id == expenditure_id, Expenditure.tower_id == tower_id
        )
    )
    if expenditure is None:
        raise AppError(404, "EXPENDITURE_NOT_FOUND", "Expenditure not found.")
    return ExpenditureOut.model_validate(expenditure)


@router.put("/{expenditure_id}", response_model=ExpenditureOut)
async def update_expenditure(
    tower_id: UUID,
    expenditure_id: UUID,
    payload: ExpenditureUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("MANAGE_EXPENDITURE")),
) -> ExpenditureOut:
    expenditure = await db.scalar(
        select(Expenditure).where(
            Expenditure.id == expenditure_id, Expenditure.tower_id == tower_id
        )
    )
    if expenditure is None:
        raise AppError(404, "EXPENDITURE_NOT_FOUND", "Expenditure not found.")
    if expenditure.deactivated_at is not None:
        raise AppError(409, "EXPENDITURE_DELETED", "Cannot edit a deleted expenditure.")

    before = _snapshot(expenditure)
    if payload.expenditure_date is not None:
        expenditure.expenditure_date = payload.expenditure_date
    if payload.category is not None:
        expenditure.category = payload.category.value
    if payload.description is not None:
        expenditure.description = payload.description
    if payload.vendor_payee_name is not None:
        expenditure.vendor_payee_name = payload.vendor_payee_name
    if payload.amount is not None:
        expenditure.amount = payload.amount
    if payload.payment_mode is not None:
        expenditure.payment_mode = payload.payment_mode
    if payload.attachment_s3_key is not None:
        expenditure.attachment_s3_key = payload.attachment_s3_key
    after = _snapshot(expenditure)

    await write_audit_log(
        db,
        actor=current_user,
        tower_id=tower_id,
        action="EXPENDITURE_UPDATED",
        entity_type="Expenditure",
        entity_id=expenditure.id,
        before=before,
        after=after,
    )
    await db.commit()
    await db.refresh(expenditure)
    return ExpenditureOut.model_validate(expenditure)


@router.delete("/{expenditure_id}", response_model=ExpenditureOut)
async def delete_expenditure(
    tower_id: UUID,
    expenditure_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("MANAGE_EXPENDITURE")),
) -> ExpenditureOut:
    expenditure = await db.scalar(
        select(Expenditure).where(
            Expenditure.id == expenditure_id, Expenditure.tower_id == tower_id
        )
    )
    if expenditure is None:
        raise AppError(404, "EXPENDITURE_NOT_FOUND", "Expenditure not found.")
    if expenditure.deactivated_at is not None:
        raise AppError(409, "EXPENDITURE_DELETED", "Expenditure already deleted.")

    before = {"deactivated_at": None}
    expenditure.deactivated_at = datetime.now(UTC)
    after = {"deactivated_at": expenditure.deactivated_at.isoformat()}

    await write_audit_log(
        db,
        actor=current_user,
        tower_id=tower_id,
        action="EXPENDITURE_DELETED",
        entity_type="Expenditure",
        entity_id=expenditure.id,
        before=before,
        after=after,
    )
    await db.commit()
    await db.refresh(expenditure)
    return ExpenditureOut.model_validate(expenditure)


@router.get("/{expenditure_id}/attachment", response_model=AttachmentUrlResponse)
async def get_expenditure_attachment_url(
    tower_id: UUID,
    expenditure_id: UUID,
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("VIEW_TOWER_DATA")),
) -> AttachmentUrlResponse:
    expenditure = await db.scalar(
        select(Expenditure).where(
            Expenditure.id == expenditure_id, Expenditure.tower_id == tower_id
        )
    )
    if expenditure is None:
        raise AppError(404, "EXPENDITURE_NOT_FOUND", "Expenditure not found.")
    if expenditure.attachment_s3_key is None:
        raise AppError(404, "ATTACHMENT_NOT_FOUND", "This expenditure has no attachment.")

    url = generate_get_url(s3_key=expenditure.attachment_s3_key)
    return AttachmentUrlResponse(url=url)
