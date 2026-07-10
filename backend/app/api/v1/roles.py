from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.deps import get_current_user, require_permission
from app.core.errors import AppError
from app.core.pagination import Pagination, pagination_params
from app.db.session import get_db
from app.models.association_member import AssociationMember
from app.models.permission import Permission
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.user import User
from app.schemas.common import PageEnvelope
from app.schemas.role import CreateRoleRequest, RoleOut, UpdateRoleRequest
from app.services.audit import write_audit_log

router = APIRouter(prefix="/towers/{tower_id}/roles", tags=["roles"])


def _to_role_out(role: Role) -> RoleOut:
    out = RoleOut.model_validate(role)
    out.permission_codes = sorted(p.code for p in role.permissions)
    return out


@router.get("", response_model=PageEnvelope[RoleOut])
async def list_roles(
    tower_id: UUID,
    pagination: Pagination = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("VIEW_TOWER_DATA")),
) -> PageEnvelope[RoleOut]:
    total = await db.scalar(select(func.count()).select_from(Role).where(Role.tower_id == tower_id))
    rows = (
        (
            await db.execute(
                select(Role)
                .where(Role.tower_id == tower_id)
                .options(joinedload(Role.permissions))
                .order_by(Role.created_at.asc())
                .offset(pagination.offset)
                .limit(pagination.page_size)
            )
        )
        .unique()
        .scalars()
        .all()
    )
    return PageEnvelope(
        items=[_to_role_out(r) for r in rows],
        page=pagination.page,
        page_size=pagination.page_size,
        total=total or 0,
    )


@router.post("", response_model=RoleOut, status_code=201)
async def create_role(
    tower_id: UUID,
    payload: CreateRoleRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("MANAGE_ASSOCIATION_MEMBERS")),
) -> RoleOut:
    existing = await db.scalar(
        select(Role).where(Role.tower_id == tower_id, Role.name == payload.name)
    )
    if existing is not None:
        raise AppError(
            409, "ROLE_NAME_TAKEN", "A role with this name already exists for this tower."
        )

    permissions = (
        (await db.execute(select(Permission).where(Permission.code.in_(payload.permission_codes))))
        .scalars()
        .all()
    )
    found_codes = {p.code for p in permissions}
    unknown = set(payload.permission_codes) - found_codes
    if unknown:
        raise AppError(
            422,
            "VALIDATION_ERROR",
            "Unknown permission code(s).",
            field_errors={"permission_codes": f"Unknown codes: {sorted(unknown)}"},
        )

    role = Role(tower_id=tower_id, name=payload.name, is_system_default=False)
    db.add(role)
    await db.flush()
    for perm in permissions:
        db.add(RolePermission(role_id=role.id, permission_id=perm.id))
    await db.flush()

    await write_audit_log(
        db,
        actor=current_user,
        tower_id=tower_id,
        action="ROLE_CREATED",
        entity_type="Role",
        entity_id=role.id,
        before=None,
        after={"name": role.name, "permission_codes": sorted(found_codes)},
    )
    await db.commit()
    await db.refresh(role, attribute_names=["permissions"])
    return _to_role_out(role)


@router.put("/{role_id}", response_model=RoleOut)
async def update_role(
    tower_id: UUID,
    role_id: UUID,
    payload: UpdateRoleRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("MANAGE_ASSOCIATION_MEMBERS")),
) -> RoleOut:
    role = await db.scalar(
        select(Role)
        .where(Role.id == role_id, Role.tower_id == tower_id)
        .options(joinedload(Role.permissions))
    )
    if role is None:
        raise AppError(404, "ROLE_NOT_FOUND", "Role not found.")
    if role.is_system_default:
        raise AppError(409, "ROLE_IMMUTABLE", "The system-default Admin role cannot be modified.")

    before_codes = sorted(p.code for p in role.permissions)

    if payload.name is not None:
        role.name = payload.name

    if payload.permission_codes is not None:
        permissions = (
            (
                await db.execute(
                    select(Permission).where(Permission.code.in_(payload.permission_codes))
                )
            )
            .scalars()
            .all()
        )
        found_codes = {p.code for p in permissions}
        unknown = set(payload.permission_codes) - found_codes
        if unknown:
            raise AppError(
                422,
                "VALIDATION_ERROR",
                "Unknown permission code(s).",
                field_errors={"permission_codes": f"Unknown codes: {sorted(unknown)}"},
            )
        await db.execute(delete(RolePermission).where(RolePermission.role_id == role.id))
        for perm in permissions:
            db.add(RolePermission(role_id=role.id, permission_id=perm.id))

    await db.flush()
    await db.refresh(role, attribute_names=["permissions"])
    after_codes = sorted(p.code for p in role.permissions)

    await write_audit_log(
        db,
        actor=current_user,
        tower_id=tower_id,
        action="ROLE_PERMISSIONS_UPDATED",
        entity_type="Role",
        entity_id=role.id,
        before={"permission_codes": before_codes},
        after={"permission_codes": after_codes},
    )
    await db.commit()
    await db.refresh(role, attribute_names=["permissions"])
    return _to_role_out(role)


@router.post("/{role_id}/deactivate", response_model=RoleOut)
async def deactivate_role(
    tower_id: UUID,
    role_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _member=Depends(require_permission("MANAGE_ASSOCIATION_MEMBERS")),
) -> RoleOut:
    role = await db.scalar(
        select(Role)
        .where(Role.id == role_id, Role.tower_id == tower_id)
        .options(joinedload(Role.permissions))
    )
    if role is None:
        raise AppError(404, "ROLE_NOT_FOUND", "Role not found.")
    if role.is_system_default:
        raise AppError(
            409, "ROLE_IMMUTABLE", "The system-default Admin role cannot be deactivated."
        )

    active_members = await db.scalar(
        select(func.count())
        .select_from(AssociationMember)
        .where(
            AssociationMember.role_id == role.id,
            AssociationMember.deactivated_at.is_(None),
        )
    )
    if active_members and active_members > 0:
        raise AppError(
            409, "ROLE_IN_USE", "This role is still held by one or more active association members."
        )

    before = {"deactivated_at": None}
    role.deactivated_at = datetime.now(UTC)
    after = {"deactivated_at": role.deactivated_at.isoformat()}

    await write_audit_log(
        db,
        actor=current_user,
        tower_id=tower_id,
        action="ROLE_DEACTIVATED",
        entity_type="Role",
        entity_id=role.id,
        before=before,
        after=after,
    )
    await db.commit()
    await db.refresh(role, attribute_names=["permissions"])
    return _to_role_out(role)
