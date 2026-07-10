"""Small factory helpers shared across the test suite — no ORM magic, just explicit inserts
so tests read top-to-bottom without hunting through fixture indirection."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import PERMISSION_CATALOG
from app.models.apartment_complex import ApartmentComplex
from app.models.association_member import AssociationMember
from app.models.permission import Permission
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.tower import Tower
from app.models.user import User
from app.services.security import hash_password

DEFAULT_PASSWORD = "CorrectHorseBatteryStaple1!"


async def make_user(
    db: AsyncSession,
    *,
    email: str,
    password: str = DEFAULT_PASSWORD,
    is_superuser: bool = False,
    account_type: str = "tower_admin",
) -> User:
    user = User(
        email=email,
        hashed_password=hash_password(password),
        account_type=account_type,
        is_superuser=is_superuser,
    )
    db.add(user)
    await db.flush()
    return user


async def make_complex(db: AsyncSession, *, name: str = "Sunrise Complex") -> ApartmentComplex:
    complex_row = ApartmentComplex(name=name, address="1 Example Street")
    db.add(complex_row)
    await db.flush()
    return complex_row


async def make_tower(
    db: AsyncSession, *, complex_id: UUID, name: str = "Oak Tower", code: str | None = None
) -> Tower:
    tower = Tower(
        complex_id=complex_id,
        name=name,
        code=code or name[:3].upper(),
        total_floors=10,
        total_flats=40,
        association_name=f"{name} Owners Association",
    )
    db.add(tower)
    await db.flush()
    return tower


async def make_role(
    db: AsyncSession,
    *,
    tower_id: UUID,
    name: str = "Admin",
    is_system_default: bool = False,
    permission_codes: list[str] | None = None,
) -> Role:
    role = Role(tower_id=tower_id, name=name, is_system_default=is_system_default)
    db.add(role)
    await db.flush()

    codes = permission_codes if permission_codes is not None else [c for c, _ in PERMISSION_CATALOG]
    perms = (await db.execute(select(Permission).where(Permission.code.in_(codes)))).scalars().all()
    for perm in perms:
        db.add(RolePermission(role_id=role.id, permission_id=perm.id))
    await db.flush()
    return role


async def make_association_member(
    db: AsyncSession,
    *,
    tower_id: UUID,
    user_id: UUID,
    role_id: UUID,
    name: str = "Test Member",
    phone: str = "9876543210",
) -> AssociationMember:
    member = AssociationMember(
        tower_id=tower_id, user_id=user_id, role_id=role_id, name=name, phone=phone
    )
    db.add(member)
    await db.flush()
    return member
