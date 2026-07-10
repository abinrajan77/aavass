"""Module 3/4 (maintenance dues / special-collection dues) don't exist in this codebase yet,
so `tower_has_active_financials()` (app/services/tower.py) is stubbed to always return
False — see its TODO(module-3/4) docstring. This means the real
`409 TOWER_HAS_ACTIVE_FINANCIALS` scenario from overview.md's acceptance criterion 8 (an
Overdue due blocking deactivation) cannot be constructed against this module alone. These
tests assert the *current, documented* stub behavior (deactivation always succeeds) plus the
surrounding guard rails that ARE fully implemented here (superuser-only reactivate, audit log
on deactivate/reactivate) — they must be revisited once Module 3/4 land and the stub is
replaced with a real query.
"""

import pytest

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
async def test_deactivate_succeeds_under_current_stub_and_sets_deactivated_at(client, db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    admin_role = await make_role(
        db_session,
        tower_id=tower.id,
        name="Admin",
        is_system_default=True,
        permission_codes=["MANAGE_COMPLEX", "VIEW_TOWER_DATA"],
    )
    admin_user = await make_user(db_session, email="deactivate-admin@example.com")
    await make_association_member(
        db_session, tower_id=tower.id, user_id=admin_user.id, role_id=admin_role.id
    )
    await db_session.commit()

    await _login(client, admin_user.email)

    resp = await client.post(f"/api/v1/towers/{tower.id}/deactivate")
    assert resp.status_code == 200
    assert resp.json()["deactivated_at"] is not None


@pytest.mark.asyncio
async def test_reactivate_requires_superuser_not_tower_admin(client, db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    admin_role = await make_role(
        db_session,
        tower_id=tower.id,
        name="Admin",
        is_system_default=True,
        permission_codes=["MANAGE_COMPLEX", "VIEW_TOWER_DATA"],
    )
    admin_user = await make_user(db_session, email="reactivate-admin@example.com")
    await make_association_member(
        db_session, tower_id=tower.id, user_id=admin_user.id, role_id=admin_role.id
    )
    await db_session.commit()

    await _login(client, admin_user.email)
    await client.post(f"/api/v1/towers/{tower.id}/deactivate")

    resp = await client.post(f"/api/v1/towers/{tower.id}/reactivate")
    assert resp.status_code == 403

    superuser = await make_user(
        db_session, email="reactivate-super@aavaas.internal", is_superuser=True
    )
    await db_session.commit()
    await _login(client, superuser.email)
    resp2 = await client.post(f"/api/v1/towers/{tower.id}/reactivate")
    assert resp2.status_code == 200
    assert resp2.json()["deactivated_at"] is None
