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
from app.models.billing_cycle import BillingCycle
from app.models.flat import Flat
from app.models.flat_ownership import FlatOwnership
from app.models.grace_period_config import GracePeriodConfig
from app.models.maintenance_formula import MaintenanceFormula
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


async def make_primary_owner_for_flat(
    db: AsyncSession,
    *,
    flat_id: UUID,
    created_by_user_id: UUID,
    full_name: str = "Asha Rao",
    phone: str = "9876500000",
) -> Owner:
    """Module 3 test convenience: an `Owner` is no longer flat-scoped (see `app/models/owner.py`
    — ownership lives on `FlatOwnership`), so Module 3's billing tests (which only care about
    "this flat's primary owner", not co-ownership/history) go through this one-call helper
    instead of each test wiring up `make_owner` + `make_flat_ownership` separately."""
    owner = await make_owner(db, full_name=full_name, phone=phone)
    await make_flat_ownership(
        db,
        flat_id=flat_id,
        owner_id=owner.id,
        created_by_user_id=created_by_user_id,
        is_primary_contact=True,
    )
    return owner


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


async def make_maintenance_formula(
    db: AsyncSession,
    *,
    tower_id: UUID,
    created_by: UUID,
    base_amount: Decimal = Decimal("2000.00"),
    per_sqft_rate: Decimal = Decimal("2.00"),
    effective_from: date | None = None,
) -> MaintenanceFormula:
    formula = MaintenanceFormula(
        tower_id=tower_id,
        base_amount=base_amount,
        per_sqft_rate=per_sqft_rate,
        effective_from=effective_from or date.today(),
        created_by=created_by,
    )
    db.add(formula)
    await db.flush()
    return formula


async def make_grace_period_config(
    db: AsyncSession,
    *,
    tower_id: UUID,
    created_by: UUID,
    grace_period_days: int = 5,
    effective_from: date | None = None,
) -> GracePeriodConfig:
    config = GracePeriodConfig(
        tower_id=tower_id,
        grace_period_days=grace_period_days,
        effective_from=effective_from or date.today(),
        created_by=created_by,
    )
    db.add(config)
    await db.flush()
    return config


async def make_billing_cycle(
    db: AsyncSession,
    *,
    tower_id: UUID,
    formula_id: UUID,
    created_by: UUID,
    month: int = 7,
    year: int = 2026,
    due_date: date | None = None,
    grace_period_days_snapshot: int = 5,
    status: str = "active",
) -> BillingCycle:
    cycle = BillingCycle(
        tower_id=tower_id,
        month=month,
        year=year,
        due_date=due_date or date(year, month, 10),
        formula_id=formula_id,
        grace_period_days_snapshot=grace_period_days_snapshot,
        status=status,
        created_by=created_by,
    )
    db.add(cycle)
    await db.flush()
    return cycle


async def make_billing_admin(
    db: AsyncSession,
    *,
    tower_id: UUID,
    email: str,
    permission_codes: list[str] | None = None,
) -> AssociationMember:
    """Convenience wrapper for the common Module 3 integration-test setup: a user + role +
    association member holding the billing permissions (`CONFIGURE_BILLING`,
    `CREATE_BILLING_CYCLE`, `RECORD_PAYMENT`, `VIEW_TOWER_DATA`) needed to exercise this
    module's endpoints end-to-end."""
    codes = permission_codes or [
        "CONFIGURE_BILLING",
        "CREATE_BILLING_CYCLE",
        "RECORD_PAYMENT",
        "VIEW_TOWER_DATA",
    ]
    role = await make_role(
        db, tower_id=tower_id, name=f"BillingAdmin-{email}", permission_codes=codes
    )
    user = await make_user(db, email=email)
    return await make_association_member(db, tower_id=tower_id, user_id=user.id, role_id=role.id)
