from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_superuser
from app.core.errors import AppError
from app.core.pagination import Pagination, pagination_params
from app.db.session import get_db
from app.models.apartment_complex import ApartmentComplex
from app.schemas.common import PageEnvelope
from app.schemas.complex import ComplexOut, CreateComplexRequest, UpdateComplexRequest

router = APIRouter(
    prefix="/complexes", tags=["complexes"], dependencies=[Depends(require_superuser)]
)


@router.post("", response_model=ComplexOut, status_code=201)
async def create_complex(
    payload: CreateComplexRequest,
    db: AsyncSession = Depends(get_db),
) -> ComplexOut:
    complex_row = ApartmentComplex(name=payload.name, address=payload.address)
    db.add(complex_row)
    await db.commit()
    await db.refresh(complex_row)
    return ComplexOut.model_validate(complex_row)


@router.get("", response_model=PageEnvelope[ComplexOut])
async def list_complexes(
    pagination: Pagination = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
) -> PageEnvelope[ComplexOut]:
    total = await db.scalar(select(func.count()).select_from(ApartmentComplex))
    rows = (
        (
            await db.execute(
                select(ApartmentComplex)
                .order_by(ApartmentComplex.created_at.desc())
                .offset(pagination.offset)
                .limit(pagination.page_size)
            )
        )
        .scalars()
        .all()
    )
    return PageEnvelope(
        items=[ComplexOut.model_validate(r) for r in rows],
        page=pagination.page,
        page_size=pagination.page_size,
        total=total or 0,
    )


@router.get("/{complex_id}", response_model=ComplexOut)
async def get_complex(complex_id: UUID, db: AsyncSession = Depends(get_db)) -> ComplexOut:
    complex_row = await db.get(ApartmentComplex, complex_id)
    if complex_row is None:
        raise AppError(404, "COMPLEX_NOT_FOUND", "Complex not found.")
    return ComplexOut.model_validate(complex_row)


@router.put("/{complex_id}", response_model=ComplexOut)
async def update_complex(
    complex_id: UUID,
    payload: UpdateComplexRequest,
    db: AsyncSession = Depends(get_db),
) -> ComplexOut:
    complex_row = await db.get(ApartmentComplex, complex_id)
    if complex_row is None:
        raise AppError(404, "COMPLEX_NOT_FOUND", "Complex not found.")
    if payload.name is not None:
        complex_row.name = payload.name
    if payload.address is not None:
        complex_row.address = payload.address
    await db.commit()
    await db.refresh(complex_row)
    return ComplexOut.model_validate(complex_row)
