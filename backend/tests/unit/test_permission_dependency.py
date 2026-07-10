"""Unit tests for `require_permission()` / `require_superuser()` — the core RBAC dependency
described in backend.md's pseudocode. Exercised directly (not via HTTP) against a real DB
session so the AssociationMember/Role/Permission joins are real, but without going through
routing/serialization overhead.
"""

from dataclasses import dataclass
from datetime import UTC

import pytest

from app.api.deps import require_permission, require_superuser
from app.core.errors import AppError
from tests.factories import make_association_member, make_complex, make_role, make_tower, make_user


@dataclass
class FakeRequest:
    method: str = "GET"


async def _call(dep, *, request, tower_id, current_user, db):
    return await dep(request=request, tower_id=tower_id, current_user=current_user, db=db)


@pytest.mark.asyncio
async def test_allows_user_whose_role_has_the_required_permission(db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    role = await make_role(
        db_session, tower_id=tower.id, name="Treasurer", permission_codes=["RECORD_PAYMENT"]
    )
    user = await make_user(db_session, email="treasurer@example.com")
    await make_association_member(db_session, tower_id=tower.id, user_id=user.id, role_id=role.id)

    dep = require_permission("RECORD_PAYMENT")
    member = await _call(
        dep, request=FakeRequest("POST"), tower_id=tower.id, current_user=user, db=db_session
    )
    assert member is not None
    assert member.user_id == user.id


@pytest.mark.asyncio
async def test_denies_user_whose_role_lacks_the_required_permission(db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    role = await make_role(
        db_session, tower_id=tower.id, name="ReadOnly", permission_codes=["VIEW_TOWER_DATA"]
    )
    user = await make_user(db_session, email="readonly@example.com")
    await make_association_member(db_session, tower_id=tower.id, user_id=user.id, role_id=role.id)

    dep = require_permission("CREATE_BILLING_CYCLE")
    with pytest.raises(AppError) as exc_info:
        await _call(
            dep, request=FakeRequest("POST"), tower_id=tower.id, current_user=user, db=db_session
        )
    assert exc_info.value.status_code == 403
    assert exc_info.value.error_code == "PERMISSION_DENIED"


@pytest.mark.asyncio
async def test_returns_tower_access_denied_for_user_with_zero_memberships(db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    user = await make_user(db_session, email="nobody@example.com")

    dep = require_permission("VIEW_TOWER_DATA")
    with pytest.raises(AppError) as exc_info:
        await _call(
            dep, request=FakeRequest("GET"), tower_id=tower.id, current_user=user, db=db_session
        )
    assert exc_info.value.status_code == 403
    assert exc_info.value.error_code == "TOWER_ACCESS_DENIED"


@pytest.mark.asyncio
async def test_cross_tower_access_collapses_to_tower_access_denied_not_404(db_session):
    complex_row = await make_complex(db_session)
    tower_a = await make_tower(db_session, complex_id=complex_row.id, name="Tower A", code="TWA")
    tower_b = await make_tower(db_session, complex_id=complex_row.id, name="Tower B", code="TWB")
    role_a = await make_role(db_session, tower_id=tower_a.id, name="Admin A")
    user = await make_user(db_session, email="tower-a-admin@example.com")
    await make_association_member(
        db_session, tower_id=tower_a.id, user_id=user.id, role_id=role_a.id
    )

    dep = require_permission("VIEW_TOWER_DATA")
    with pytest.raises(AppError) as exc_info:
        await _call(
            dep, request=FakeRequest("GET"), tower_id=tower_b.id, current_user=user, db=db_session
        )
    assert exc_info.value.status_code == 403
    assert exc_info.value.error_code == "TOWER_ACCESS_DENIED"


@pytest.mark.asyncio
async def test_superuser_bypasses_tower_rbac_entirely(db_session):
    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    superuser = await make_user(db_session, email="ops@aavaas.internal", is_superuser=True)

    dep = require_permission("CREATE_BILLING_CYCLE")
    # Superuser has no AssociationMember row anywhere, yet must not be denied.
    result = await _call(
        dep, request=FakeRequest("POST"), tower_id=tower.id, current_user=superuser, db=db_session
    )
    assert result is None  # per pseudocode: superuser bypass returns None


@pytest.mark.asyncio
async def test_tower_inactive_blocks_mutating_call_but_allows_read(db_session):
    from datetime import datetime

    complex_row = await make_complex(db_session)
    tower = await make_tower(db_session, complex_id=complex_row.id)
    tower.deactivated_at = datetime.now(UTC)
    role = await make_role(
        db_session, tower_id=tower.id, name="Admin", permission_codes=["MANAGE_COMPLEX"]
    )
    user = await make_user(db_session, email="admin@example.com")
    await make_association_member(db_session, tower_id=tower.id, user_id=user.id, role_id=role.id)

    dep = require_permission("MANAGE_COMPLEX")

    with pytest.raises(AppError) as exc_info:
        await _call(
            dep, request=FakeRequest("POST"), tower_id=tower.id, current_user=user, db=db_session
        )
    assert exc_info.value.status_code == 409
    assert exc_info.value.error_code == "TOWER_INACTIVE"

    # GET (read) on the same deactivated tower must be allowed through.
    member = await _call(
        dep, request=FakeRequest("GET"), tower_id=tower.id, current_user=user, db=db_session
    )
    assert member is not None


@pytest.mark.asyncio
async def test_require_superuser_denies_non_superuser(db_session):
    user = await make_user(db_session, email="regular@example.com")
    with pytest.raises(AppError) as exc_info:
        await require_superuser(current_user=user)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_require_superuser_allows_superuser(db_session):
    user = await make_user(db_session, email="ops2@aavaas.internal", is_superuser=True)
    result = await require_superuser(current_user=user)
    assert result is user
