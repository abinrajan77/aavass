import secrets
import string
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.deps import get_current_user, require_permission
from app.core.errors import AppError
from app.core.pagination import Pagination, pagination_params
from app.db.session import get_db
from app.models.association_member import AssociationMember
from app.models.role import Role
from app.models.user import User
from app.schemas.association_member import (
    AssociationMemberOut,
    CreateAssociationMemberRequest,
    CreateAssociationMemberResponse,
    UpdateAssociationMemberRequest,
)
from app.schemas.common import PageEnvelope
from app.services.audit import write_audit_log
from app.services.security import hash_password

router = APIRouter(prefix="/towers/{tower_id}/association-members", tags=["association-members"])

_TEMP_PASSWORD_ALPHABET = string.ascii_letters + string.digits + "!@#$%"


def _generate_temp_password(length: int = 14) -> str:
    return "".join(secrets.choice(_TEMP_PASSWORD_ALPHABET) for _ in range(length))


@router.get("", response_model=PageEnvelope[AssociationMemberOut])
async def list_association_members(
    tower_id: UUID,
    pagination: Pagination = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("VIEW_TOWER_DATA")),
) -> PageEnvelope[AssociationMemberOut]:
    total = await db.scalar(
        select(func.count())
        .select_from(AssociationMember)
        .where(AssociationMember.tower_id == tower_id)
    )
    rows = (
        (
            await db.execute(
                select(AssociationMember)
                .where(AssociationMember.tower_id == tower_id)
                .order_by(AssociationMember.created_at.asc())
                .offset(pagination.offset)
                .limit(pagination.page_size)
            )
        )
        .scalars()
        .all()
    )
    return PageEnvelope(
        items=[AssociationMemberOut.model_validate(r) for r in rows],
        page=pagination.page,
        page_size=pagination.page_size,
        total=total or 0,
    )


@router.post("", response_model=CreateAssociationMemberResponse, status_code=201)
async def create_association_member(
    tower_id: UUID,
    payload: CreateAssociationMemberRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("MANAGE_ASSOCIATION_MEMBERS")),
) -> CreateAssociationMemberResponse:
    role = await db.scalar(
        select(Role).where(Role.id == payload.role_id, Role.tower_id == tower_id)
    )
    if role is None:
        raise AppError(
            422,
            "VALIDATION_ERROR",
            "Role not found for this tower.",
            field_errors={"role_id": "Role does not exist in this tower."},
        )

    # Email reused across account types: link the existing User rather than error on
    # duplicate email (an owner can also be an association member — see overview.md).
    user = await db.scalar(select(User).where(User.email == payload.email))
    temp_password = _generate_temp_password()
    if user is None:
        user = User(
            email=payload.email,
            hashed_password=hash_password(temp_password),
            account_type="tower_admin",
            force_password_change=True,
        )
        db.add(user)
        await db.flush()
    else:
        existing_member = await db.scalar(
            select(AssociationMember).where(
                AssociationMember.tower_id == tower_id, AssociationMember.user_id == user.id
            )
        )
        if existing_member is not None:
            raise AppError(
                409,
                "MEMBER_ALREADY_EXISTS",
                "This user is already an association member of this tower.",
            )
        # Existing user (e.g. a flat owner) is being additionally provisioned as an
        # association member — reset their password to a fresh temp password and force
        # a change, consistent with the "one-time temporary password" contract.
        user.hashed_password = hash_password(temp_password)
        user.force_password_change = True

    member = AssociationMember(
        tower_id=tower_id,
        user_id=user.id,
        role_id=payload.role_id,
        name=payload.name,
        phone=payload.phone,
    )
    db.add(member)
    await db.flush()

    await write_audit_log(
        db,
        actor=current_user,
        tower_id=tower_id,
        action="ASSOCIATION_MEMBER_CREATED",
        entity_type="AssociationMember",
        entity_id=member.id,
        before=None,
        after={"name": member.name, "email": payload.email, "role_id": str(payload.role_id)},
    )
    await db.commit()
    await db.refresh(member)
    return CreateAssociationMemberResponse(
        association_member=AssociationMemberOut.model_validate(member),
        temporary_password=temp_password,
    )


@router.put("/{member_id}", response_model=AssociationMemberOut)
async def update_association_member(
    tower_id: UUID,
    member_id: UUID,
    payload: UpdateAssociationMemberRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("MANAGE_ASSOCIATION_MEMBERS")),
) -> AssociationMemberOut:
    member = await db.scalar(
        select(AssociationMember).where(
            AssociationMember.id == member_id, AssociationMember.tower_id == tower_id
        )
    )
    if member is None:
        raise AppError(404, "MEMBER_NOT_FOUND", "Association member not found.")

    if payload.role_id is not None:
        role = await db.scalar(
            select(Role).where(Role.id == payload.role_id, Role.tower_id == tower_id)
        )
        if role is None:
            raise AppError(
                422,
                "VALIDATION_ERROR",
                "Role not found for this tower.",
                field_errors={"role_id": "Role does not exist in this tower."},
            )

    before = {"name": member.name, "phone": member.phone, "role_id": str(member.role_id)}
    if payload.name is not None:
        member.name = payload.name
    if payload.phone is not None:
        member.phone = payload.phone
    if payload.role_id is not None:
        member.role_id = payload.role_id
    after = {"name": member.name, "phone": member.phone, "role_id": str(member.role_id)}

    await write_audit_log(
        db,
        actor=current_user,
        tower_id=tower_id,
        action="ASSOCIATION_MEMBER_UPDATED",
        entity_type="AssociationMember",
        entity_id=member.id,
        before=before,
        after=after,
    )
    await db.commit()
    await db.refresh(member)
    return AssociationMemberOut.model_validate(member)


@router.post("/{member_id}/deactivate", response_model=AssociationMemberOut)
async def deactivate_association_member(
    tower_id: UUID,
    member_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("MANAGE_ASSOCIATION_MEMBERS")),
) -> AssociationMemberOut:
    member = await db.scalar(
        select(AssociationMember)
        .where(AssociationMember.id == member_id, AssociationMember.tower_id == tower_id)
        .options(joinedload(AssociationMember.role))
    )
    if member is None:
        raise AppError(404, "MEMBER_NOT_FOUND", "Association member not found.")

    if member.deactivated_at is None and member.role.is_system_default:
        other_active_admins = await db.scalar(
            select(func.count())
            .select_from(AssociationMember)
            .join(Role, Role.id == AssociationMember.role_id)
            .where(
                AssociationMember.tower_id == tower_id,
                AssociationMember.deactivated_at.is_(None),
                AssociationMember.id != member.id,
                Role.is_system_default.is_(True),
            )
        )
        if not other_active_admins:
            raise AppError(
                409,
                "LAST_ADMIN",
                "Cannot deactivate the tower's only active Admin-role member.",
            )

    before = {"deactivated_at": None}
    member.deactivated_at = datetime.now(UTC)
    after = {"deactivated_at": member.deactivated_at.isoformat()}

    await write_audit_log(
        db,
        actor=current_user,
        tower_id=tower_id,
        action="ASSOCIATION_MEMBER_DEACTIVATED",
        entity_type="AssociationMember",
        entity_id=member.id,
        before=before,
        after=after,
    )
    await db.commit()
    await db.refresh(member)
    return AssociationMemberOut.model_validate(member)
