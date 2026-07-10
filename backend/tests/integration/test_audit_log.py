import pytest
from sqlalchemy import func, select

from app.models.audit_log import AuditLog
from tests.factories import (
    DEFAULT_PASSWORD,
    make_association_member,
    make_complex,
    make_role,
    make_tower,
    make_user,
)


async def _login(client, email, password=DEFAULT_PASSWORD):
    return await client.post("/api/v1/auth/login", json={"email": email, "password": password})


@pytest.mark.asyncio
async def test_role_permissions_change_writes_audit_log_with_correct_before_after(
    client, db_session
):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    custom_role = await make_role(
        db_session,
        tower_id=tower.id,
        name="Treasurer",
        permission_codes=["RECORD_PAYMENT", "VIEW_TOWER_DATA"],
    )
    admin_role = await make_role(
        db_session,
        tower_id=tower.id,
        name="Admin",
        is_system_default=True,
        permission_codes=["MANAGE_ASSOCIATION_MEMBERS", "VIEW_TOWER_DATA"],
    )
    admin_user = await make_user(db_session, email="audit-admin@example.com")
    await make_association_member(
        db_session, tower_id=tower.id, user_id=admin_user.id, role_id=admin_role.id
    )
    await db_session.commit()

    await _login(client, admin_user.email)

    resp = await client.put(
        f"/api/v1/towers/{tower.id}/roles/{custom_role.id}",
        json={"permission_codes": ["RECORD_PAYMENT"]},
    )
    assert resp.status_code == 200

    entry = await db_session.scalar(
        select(AuditLog)
        .where(AuditLog.entity_type == "Role", AuditLog.entity_id == custom_role.id)
        .order_by(AuditLog.created_at.desc())
    )
    assert entry is not None
    assert entry.action == "ROLE_PERMISSIONS_UPDATED"
    assert sorted(entry.before["permission_codes"]) == ["RECORD_PAYMENT", "VIEW_TOWER_DATA"]
    assert sorted(entry.after["permission_codes"]) == ["RECORD_PAYMENT"]
    assert entry.user_id == admin_user.id
    assert entry.actor_label == admin_user.email


@pytest.mark.asyncio
async def test_failed_transaction_leaves_no_orphaned_audit_row(db_session):
    """Simulates the write_audit_log() + entity-write atomicity contract directly: if the
    surrounding transaction is rolled back (e.g. because the entity write violated a
    constraint), the audit row must not survive either — they share one transaction."""
    from app.models.role import Role
    from app.services.audit import write_audit_log
    from tests.factories import make_user

    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    actor = await make_user(db_session, email="atomicity-actor@example.com")
    await db_session.flush()

    savepoint = await db_session.begin_nested()
    try:
        # Deliberately violate the uq_role_tower_name constraint by inserting a duplicate
        # role name for the same tower, in the same unit of work as the audit log write.
        await make_role(db_session, tower_id=tower.id, name="DupRole")
        await write_audit_log(
            db_session,
            actor=actor,
            tower_id=tower.id,
            action="ROLE_CREATED",
            entity_type="Role",
            entity_id=tower.id,  # arbitrary, not asserted on
            before=None,
            after={"name": "DupRole"},
        )
        await db_session.flush()
        # This second insert with the same tower_id/name must violate the unique constraint.
        dup_role = Role(tower_id=tower.id, name="DupRole", is_system_default=False)
        db_session.add(dup_role)
        await db_session.flush()
    except Exception:
        await savepoint.rollback()

    count = await db_session.scalar(
        select(func.count()).select_from(AuditLog).where(AuditLog.action == "ROLE_CREATED")
    )
    assert count == 0
