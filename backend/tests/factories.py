"""Small factory helpers shared across the test suite — no ORM magic, just explicit inserts
so tests read top-to-bottom without hunting through fixture indirection."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import PERMISSION_CATALOG
from app.models.apartment_complex import ApartmentComplex
from app.models.association_member import AssociationMember
from app.models.expenditure import Expenditure
from app.models.permission import Permission
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.special_collection import SpecialCollection
from app.models.tower import Tower
from app.models.user import User
from app.services.flat_directory import ActiveFlatRecord, FlatDirectory
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


async def make_special_collection(
    db: AsyncSession,
    *,
    tower_id: UUID,
    created_by: UUID,
    title: str = "Lift Modernization Fund",
    total_amount: Decimal = Decimal("100000.00"),
    due_date: date = date(2026, 9, 1),
) -> SpecialCollection:
    """Bare-row factory (no dues generated) — used by tests that only need a
    `SpecialCollection` row to exist (e.g. exercising `GET`/`DELETE` in isolation), as
    opposed to the full create-flow tests that go through `POST .../special-collections`."""
    collection = SpecialCollection(
        tower_id=tower_id, created_by=created_by, title=title, total_amount=total_amount,
        due_date=due_date,
    )
    db.add(collection)
    await db.flush()
    return collection


async def make_expenditure(
    db: AsyncSession,
    *,
    tower_id: UUID,
    recorded_by: UUID,
    expenditure_date: date = date(2026, 7, 5),
    category: str = "repairs",
    description: str = "Test expenditure",
    vendor_payee_name: str = "Test Vendor Pvt Ltd",
    amount: Decimal = Decimal("1000.00"),
    payment_mode: str = "cash",
    attachment_s3_key: str | None = None,
    is_complex_contribution: bool = False,
    complex_total_amount: Decimal | None = None,
) -> Expenditure:
    expenditure = Expenditure(
        tower_id=tower_id,
        recorded_by=recorded_by,
        expenditure_date=expenditure_date,
        category=category,
        description=description,
        vendor_payee_name=vendor_payee_name,
        amount=amount,
        payment_mode=payment_mode,
        attachment_s3_key=attachment_s3_key,
        is_complex_contribution=is_complex_contribution,
        complex_total_amount=complex_total_amount,
    )
    db.add(expenditure)
    await db.flush()
    return expenditure


_UNSET = object()


def make_active_flat_record(
    *,
    flat_number: str,
    owner_id: UUID | None = _UNSET,  # type: ignore[assignment]
    owner_name: str = "Test Owner",
    flat_id: UUID | None = None,
    no_active_owner: bool = False,
) -> ActiveFlatRecord:
    """Builds one `ActiveFlatRecord` for `FakeFlatDirectory` fixtures.

    By default mints a fresh `owner_id` (and uses `owner_name`) so most callers don't have to
    think about it. Pass `no_active_owner=True` (or `owner_id=None`) to simulate a flat with
    no active owner — backend.md test plan item 3's `NO_ACTIVE_OWNER` skip path.
    """
    if no_active_owner or owner_id is None:
        return ActiveFlatRecord(
            flat_id=flat_id or uuid4(), flat_number=flat_number, owner_id=None, owner_name=None
        )
    resolved_owner_id = owner_id if owner_id is not _UNSET else uuid4()
    return ActiveFlatRecord(
        flat_id=flat_id or uuid4(),
        flat_number=flat_number,
        owner_id=resolved_owner_id,
        owner_name=owner_name,
    )


@dataclass
class FakeFlatDirectory(FlatDirectory):
    """Test double for `app.services.flat_directory.FlatDirectory` — Module 2's real
    `Flat`/`Owner` tables don't exist yet (see that module's docstring), so integration
    tests override `app.services.flat_directory.get_flat_directory` with an instance of this
    class (seeded via `make_active_flat_record`) instead of hitting a real Module 2 query.
    This is the one seam Module 2 will eventually replace — see backend.md's build report.
    """

    flats_by_tower: dict[UUID, list[ActiveFlatRecord]] = field(default_factory=dict)

    async def list_active_flats(self, *, tower_id: UUID) -> list[ActiveFlatRecord]:
        return list(self.flats_by_tower.get(tower_id, []))
