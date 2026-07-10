from datetime import UTC, datetime
from uuid import UUID

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
from app.models.special_collection import SpecialCollection
from app.models.special_collection_due import SpecialCollectionDue
from app.models.user import User
from app.schemas.common import PageEnvelope
from app.schemas.special_collection import (
    SpecialCollectionCreate,
    SpecialCollectionDueOut,
    SpecialCollectionOut,
    SplitBasis,
)
from app.services.audit import write_audit_log
from app.services.flat_directory import FlatDirectory, get_flat_directory
from app.services.special_collection import generate_dues, rollups_for_collections

router = APIRouter(prefix="/towers/{tower_id}/special-collections", tags=["special-collections"])


def _to_out(collection: SpecialCollection, rollup: dict) -> SpecialCollectionOut:
    return SpecialCollectionOut(
        id=collection.id,
        tower_id=collection.tower_id,
        title=collection.title,
        description=collection.description,
        total_amount=collection.total_amount,
        split_basis=SplitBasis(collection.split_basis),
        due_date=collection.due_date,
        dues_generated_at=collection.dues_generated_at,
        dues_generated=collection.dues_generated_at is not None,
        skipped_flats=collection.skipped_flats or [],
        collected_amount=rollup["collected_amount"],
        pending_count=rollup["pending_count"],
        paid_count=rollup["paid_count"],
        overdue_count=rollup["overdue_count"],
        created_at=collection.created_at,
    )


@router.post("", response_model=SpecialCollectionOut, status_code=201)
async def create_special_collection(
    tower_id: UUID,
    payload: SpecialCollectionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    member: AssociationMember = Depends(
        require_permission_with_member_id("MANAGE_SPECIAL_COLLECTIONS")
    ),
    flat_directory: FlatDirectory = Depends(get_flat_directory),
) -> SpecialCollectionOut:
    collection = SpecialCollection(
        tower_id=tower_id,
        title=payload.title,
        description=payload.description,
        total_amount=payload.total_amount,
        split_basis=payload.split_basis.value,
        due_date=payload.due_date,
        created_by=member.id,
    )
    db.add(collection)
    await db.flush()

    # backend.md: >300 active flats should enqueue an SQS job (`special-collection-jobs`)
    # and return 202 instead. Not implemented in this slice (see
    # app/services/special_collection.py's module docstring) — always synchronous here.
    flats = await flat_directory.list_active_flats(tower_id=tower_id)
    await generate_dues(db, special_collection=collection, flats=flats)

    await write_audit_log(
        db,
        actor=current_user,
        tower_id=tower_id,
        action="SPECIAL_COLLECTION_CREATED",
        entity_type="SpecialCollection",
        entity_id=collection.id,
        before=None,
        after={
            "title": collection.title,
            "total_amount": str(collection.total_amount),
            "due_date": collection.due_date.isoformat(),
        },
    )
    await db.commit()
    await db.refresh(collection)

    rollup = (await rollups_for_collections(db, collection_ids=[collection.id]))[collection.id]
    return _to_out(collection, rollup)


@router.get("", response_model=PageEnvelope[SpecialCollectionOut])
async def list_special_collections(
    tower_id: UUID,
    status: str | None = None,
    pagination: Pagination = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("VIEW_TOWER_DATA")),
) -> PageEnvelope[SpecialCollectionOut]:
    if status is not None and status not in ("open", "closed"):
        raise AppError(
            422,
            "VALIDATION_ERROR",
            "status must be 'open' or 'closed'.",
            field_errors={"status": "must be 'open' or 'closed'"},
        )

    # open := at least one due not yet paid
    open_ids_subq = (
        select(SpecialCollectionDue.special_collection_id)
        .where(SpecialCollectionDue.status != "paid")
        .distinct()
    )

    query = select(SpecialCollection).where(SpecialCollection.tower_id == tower_id)
    count_query = (
        select(func.count())
        .select_from(SpecialCollection)
        .where(SpecialCollection.tower_id == tower_id)
    )
    if status == "open":
        query = query.where(SpecialCollection.id.in_(open_ids_subq))
        count_query = count_query.where(SpecialCollection.id.in_(open_ids_subq))
    elif status == "closed":
        query = query.where(SpecialCollection.id.notin_(open_ids_subq))
        count_query = count_query.where(SpecialCollection.id.notin_(open_ids_subq))

    total = await db.scalar(count_query)
    rows = (
        (
            await db.execute(
                query.order_by(SpecialCollection.created_at.desc())
                .offset(pagination.offset)
                .limit(pagination.page_size)
            )
        )
        .scalars()
        .all()
    )
    rollups = await rollups_for_collections(db, collection_ids=[r.id for r in rows])
    return PageEnvelope(
        items=[_to_out(r, rollups[r.id]) for r in rows],
        page=pagination.page,
        page_size=pagination.page_size,
        total=total or 0,
    )


@router.get("/{special_collection_id}", response_model=SpecialCollectionOut)
async def get_special_collection(
    tower_id: UUID,
    special_collection_id: UUID,
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("VIEW_TOWER_DATA")),
) -> SpecialCollectionOut:
    collection = await db.scalar(
        select(SpecialCollection).where(
            SpecialCollection.id == special_collection_id,
            SpecialCollection.tower_id == tower_id,
        )
    )
    if collection is None:
        raise AppError(404, "SPECIAL_COLLECTION_NOT_FOUND", "Special collection not found.")
    rollup = (await rollups_for_collections(db, collection_ids=[collection.id]))[collection.id]
    return _to_out(collection, rollup)


@router.delete("/{special_collection_id}", response_model=SpecialCollectionOut)
async def cancel_special_collection(
    tower_id: UUID,
    special_collection_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("MANAGE_SPECIAL_COLLECTIONS")),
) -> SpecialCollectionOut:
    collection = await db.scalar(
        select(SpecialCollection).where(
            SpecialCollection.id == special_collection_id,
            SpecialCollection.tower_id == tower_id,
        )
    )
    if collection is None:
        raise AppError(404, "SPECIAL_COLLECTION_NOT_FOUND", "Special collection not found.")

    paid_count = await db.scalar(
        select(func.count())
        .select_from(SpecialCollectionDue)
        .where(
            SpecialCollectionDue.special_collection_id == collection.id,
            SpecialCollectionDue.status == "paid",
        )
    )
    if paid_count:
        raise AppError(
            409,
            "IMMUTABLE_RECORD",
            "Cannot cancel a special collection with recorded payments.",
        )

    before = {"deactivated_at": None}
    collection.deactivated_at = datetime.now(UTC)
    after = {"deactivated_at": collection.deactivated_at.isoformat()}

    await write_audit_log(
        db,
        actor=current_user,
        tower_id=tower_id,
        action="SPECIAL_COLLECTION_CANCELLED",
        entity_type="SpecialCollection",
        entity_id=collection.id,
        before=before,
        after=after,
    )
    await db.commit()
    await db.refresh(collection)
    rollup = (await rollups_for_collections(db, collection_ids=[collection.id]))[collection.id]
    return _to_out(collection, rollup)


@router.get(
    "/{special_collection_id}/dues", response_model=PageEnvelope[SpecialCollectionDueOut]
)
async def list_special_collection_dues(
    tower_id: UUID,
    special_collection_id: UUID,
    status: str | None = None,
    flat_id: UUID | None = None,
    owner_id: UUID | None = None,
    pagination: Pagination = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("VIEW_TOWER_DATA")),
) -> PageEnvelope[SpecialCollectionDueOut]:
    collection = await db.scalar(
        select(SpecialCollection).where(
            SpecialCollection.id == special_collection_id,
            SpecialCollection.tower_id == tower_id,
        )
    )
    if collection is None:
        raise AppError(404, "SPECIAL_COLLECTION_NOT_FOUND", "Special collection not found.")

    filters = [SpecialCollectionDue.special_collection_id == special_collection_id]
    if status is not None:
        filters.append(SpecialCollectionDue.status == status)
    if flat_id is not None:
        filters.append(SpecialCollectionDue.flat_id == flat_id)
    if owner_id is not None:
        filters.append(SpecialCollectionDue.owner_id == owner_id)

    total = await db.scalar(
        select(func.count()).select_from(SpecialCollectionDue).where(*filters)
    )
    rows = (
        (
            await db.execute(
                select(SpecialCollectionDue)
                .where(*filters)
                .order_by(SpecialCollectionDue.created_at.asc())
                .offset(pagination.offset)
                .limit(pagination.page_size)
            )
        )
        .scalars()
        .all()
    )
    return PageEnvelope(
        items=[SpecialCollectionDueOut.model_validate(r) for r in rows],
        page=pagination.page,
        page_size=pagination.page_size,
        total=total or 0,
    )


@router.get(
    "/{special_collection_id}/dues/{due_id}", response_model=SpecialCollectionDueOut
)
async def get_special_collection_due(
    tower_id: UUID,
    special_collection_id: UUID,
    due_id: UUID,
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("VIEW_TOWER_DATA")),
) -> SpecialCollectionDueOut:
    due = await db.scalar(
        select(SpecialCollectionDue).where(
            SpecialCollectionDue.id == due_id,
            SpecialCollectionDue.special_collection_id == special_collection_id,
            SpecialCollectionDue.tower_id == tower_id,
        )
    )
    if due is None:
        raise AppError(404, "SPECIAL_COLLECTION_DUE_NOT_FOUND", "Due not found.")
    return SpecialCollectionDueOut.model_validate(due)
