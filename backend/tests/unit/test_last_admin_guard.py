"""Unit-level check of the "is this the tower's only active Admin-role member" computation
used by the association-member deactivate endpoint (`app/api/v1/association_members.py`),
across 0, 1, and 2+ other active admins — per backend.md's unit test plan.
"""

from datetime import UTC

import pytest
from sqlalchemy import func, select

from app.models.association_member import AssociationMember
from app.models.role import Role
from tests.factories import make_association_member, make_complex, make_role, make_tower, make_user


async def _other_active_admin_count(db, *, tower_id, excluding_member_id):
    return await db.scalar(
        select(func.count())
        .select_from(AssociationMember)
        .join(Role, Role.id == AssociationMember.role_id)
        .where(
            AssociationMember.tower_id == tower_id,
            AssociationMember.deactivated_at.is_(None),
            AssociationMember.id != excluding_member_id,
            Role.is_system_default.is_(True),
        )
    )


@pytest.mark.asyncio
async def test_zero_other_admins_blocks_deactivation(db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    admin_role = await make_role(
        db_session, tower_id=tower.id, name="Admin", is_system_default=True
    )
    user = await make_user(db_session, email="only-admin@example.com")
    member = await make_association_member(
        db_session, tower_id=tower.id, user_id=user.id, role_id=admin_role.id
    )

    count = await _other_active_admin_count(
        db_session, tower_id=tower.id, excluding_member_id=member.id
    )
    assert count == 0  # would raise 409 LAST_ADMIN


@pytest.mark.asyncio
async def test_one_other_admin_allows_deactivation(db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    admin_role = await make_role(
        db_session, tower_id=tower.id, name="Admin", is_system_default=True
    )
    user1 = await make_user(db_session, email="admin1@example.com")
    user2 = await make_user(db_session, email="admin2@example.com")
    member1 = await make_association_member(
        db_session, tower_id=tower.id, user_id=user1.id, role_id=admin_role.id
    )
    await make_association_member(
        db_session, tower_id=tower.id, user_id=user2.id, role_id=admin_role.id
    )

    count = await _other_active_admin_count(
        db_session, tower_id=tower.id, excluding_member_id=member1.id
    )
    assert count == 1


@pytest.mark.asyncio
async def test_two_or_more_other_admins_allows_deactivation(db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    admin_role = await make_role(
        db_session, tower_id=tower.id, name="Admin", is_system_default=True
    )
    users = [await make_user(db_session, email=f"admin{i}@example.com") for i in range(3)]
    members = [
        await make_association_member(
            db_session, tower_id=tower.id, user_id=u.id, role_id=admin_role.id
        )
        for u in users
    ]

    count = await _other_active_admin_count(
        db_session, tower_id=tower.id, excluding_member_id=members[0].id
    )
    assert count == 2


@pytest.mark.asyncio
async def test_deactivated_admins_are_not_counted(db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    admin_role = await make_role(
        db_session, tower_id=tower.id, name="Admin", is_system_default=True
    )
    user1 = await make_user(db_session, email="active-admin@example.com")
    user2 = await make_user(db_session, email="deactivated-admin@example.com")
    member1 = await make_association_member(
        db_session, tower_id=tower.id, user_id=user1.id, role_id=admin_role.id
    )
    member2 = await make_association_member(
        db_session, tower_id=tower.id, user_id=user2.id, role_id=admin_role.id
    )
    from datetime import datetime

    member2.deactivated_at = datetime.now(UTC)
    await db_session.flush()

    count = await _other_active_admin_count(
        db_session, tower_id=tower.id, excluding_member_id=member1.id
    )
    assert count == 0  # the only "other" admin is already deactivated
