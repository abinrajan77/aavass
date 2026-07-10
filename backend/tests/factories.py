"""Small factory helpers shared across the test suite — no ORM magic, just explicit inserts
so tests read top-to-bottom without hunting through fixture indirection."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import PERMISSION_CATALOG
from app.models.apartment_complex import ApartmentComplex
from app.models.association_member import AssociationMember
from app.models.flat import Flat
from app.models.flat_ownership import FlatOwnership
from app.models.owner import Owner
from app.models.permission import Permission
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.tenant import Tenant
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


async def make_flat(
    db: AsyncSession,
    *,
    tower_id: UUID,
    flat_number: str = "101",
    floor: int = 1,
    type: str = "2BHK",
    carpet_area_sqft: Decimal = Decimal("850.00"),
    occupancy_status: str = "vacant",
) -> Flat:
    flat = Flat(
        tower_id=tower_id,
        flat_number=flat_number,
        floor=floor,
        type=type,
        carpet_area_sqft=carpet_area_sqft,
        occupancy_status=occupancy_status,
    )
    db.add(flat)
    await db.flush()
    return flat


async def make_owner(
    db: AsyncSession,
    *,
    full_name: str = "Jane Owner",
    phone: str = "9876500000",
    email: str | None = None,
    id_number: str | None = None,
    user_id: UUID | None = None,
) -> Owner:
    owner = Owner(
        full_name=full_name, phone=phone, email=email, id_number=id_number, user_id=user_id
    )
    db.add(owner)
    await db.flush()
    return owner


async def make_flat_ownership(
    db: AsyncSession,
    *,
    flat_id: UUID,
    owner_id: UUID,
    created_by_user_id: UUID,
    is_primary_contact: bool = True,
    date_from: date = date(2024, 1, 1),
    date_to: date | None = None,
) -> FlatOwnership:
    ownership = FlatOwnership(
        flat_id=flat_id,
        owner_id=owner_id,
        is_primary_contact=is_primary_contact,
        date_from=date_from,
        date_to=date_to,
        created_by_user_id=created_by_user_id,
    )
    db.add(ownership)
    await db.flush()
    return ownership


async def make_tenant(
    db: AsyncSession,
    *,
    flat_id: UUID,
    full_name: str = "Tom Tenant",
    phone: str = "9123456780",
    lease_start: date = date(2024, 1, 1),
    lease_end: date | None = None,
    is_active: bool = True,
) -> Tenant:
    tenant = Tenant(
        flat_id=flat_id,
        full_name=full_name,
        phone=phone,
        lease_start=lease_start,
        lease_end=lease_end,
        is_active=is_active,
    )
    db.add(tenant)
    await db.flush()
    return tenant
