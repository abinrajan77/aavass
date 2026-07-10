# Module 1 — Auth, RBAC & Tower/Complex Setup: Backend Plan

> Companion files: [`overview.md`](./overview.md) · [`frontend.md`](./frontend.md) · [`cloud.md`](./cloud.md)
> Read `../00-architecture-and-standards.md` §5 (RBAC) and §6 (API conventions) first.

## Auth router — `/api/v1/auth` (no tower scoping; identity is tower-independent)

| Method | Path | Payload | Notes |
|---|---|---|---|
| `POST` | `/api/v1/auth/login` | `{ email, password }` | Sets `access_token` + `refresh_token` httpOnly cookies. Returns `{ user: { id, email, account_type }, permissions: string[], towers: [{ tower_id, tower_name, role_name }] }` |
| `POST` | `/api/v1/auth/refresh` | (reads `refresh_token` cookie) | Rotates refresh token (single-use), reissues both cookies |
| `POST` | `/api/v1/auth/logout` | — | Revokes the current refresh token, clears cookies |
| `GET` | `/api/v1/auth/me` | — | Returns current user + effective permissions (session hydration on page load) |
| `POST` | `/api/v1/auth/forgot-password` | `{ email }` | Always `202` regardless of whether the email exists (no user enumeration); creates a reset token |
| `POST` | `/api/v1/auth/reset-password` | `{ token, new_password }` | Invalidates the token and all existing refresh tokens for that user on success |

## Complex router — `/api/v1/complexes` (superuser only, via `require_superuser()`)

| Method | Path | Payload |
|---|---|---|
| `POST` | `/api/v1/complexes` | `{ name, address }` |
| `GET` | `/api/v1/complexes?page=&page_size=` | — (standard pagination envelope) |
| `GET` | `/api/v1/complexes/{complex_id}` | — |
| `PUT` | `/api/v1/complexes/{complex_id}` | `{ name?, address? }` |

## Tower router

| Method | Path | Payload | Guard |
|---|---|---|---|
| `POST` | `/api/v1/complexes/{complex_id}/towers` | `{ name, code, total_floors, total_flats, association_name }` | `require_superuser()` — also seeds the tower's `Admin` role with all permissions. `code` is a short unique uppercase string (e.g. `"OAK"`) used in receipt numbering by Module 3 |
| `GET` | `/api/v1/complexes/{complex_id}/towers?page=&page_size=` | — | `require_superuser()` |
| `GET` | `/api/v1/towers/{tower_id}` | — | `require_permission("VIEW_TOWER_DATA")` |
| `PUT` | `/api/v1/towers/{tower_id}` | `{ name?, total_floors?, total_flats?, association_name? }` | `require_permission("MANAGE_COMPLEX")` |
| `POST` | `/api/v1/towers/{tower_id}/deactivate` | — | `require_permission("MANAGE_COMPLEX")`; `409 TOWER_HAS_ACTIVE_FINANCIALS` if any `Pending`/`Overdue` due exists |
| `POST` | `/api/v1/towers/{tower_id}/reactivate` | — | `require_superuser()` (reactivation is a platform-level decision) |

## Association member & role router (tower-scoped)

| Method | Path | Payload | Guard |
|---|---|---|---|
| `GET` | `/api/v1/towers/{tower_id}/roles` | — | `require_permission("VIEW_TOWER_DATA")` |
| `POST` | `/api/v1/towers/{tower_id}/roles` | `{ name, permission_codes: string[] }` | `require_permission("MANAGE_ASSOCIATION_MEMBERS")` |
| `PUT` | `/api/v1/towers/{tower_id}/roles/{role_id}` | `{ name?, permission_codes? }` | same; `409 ROLE_IMMUTABLE` if `is_system_default` |
| `POST` | `/api/v1/towers/{tower_id}/roles/{role_id}/deactivate` | — | same; `409 ROLE_IN_USE` if any active member still holds it, `409 ROLE_IMMUTABLE` if system default |
| `GET` | `/api/v1/towers/{tower_id}/association-members?page=&page_size=` | — | `require_permission("VIEW_TOWER_DATA")` |
| `POST` | `/api/v1/towers/{tower_id}/association-members` | `{ name, email, phone, role_id }` | `require_permission("MANAGE_ASSOCIATION_MEMBERS")` — creates a `User` (or links an existing one by email) + the `AssociationMember` row; returns a one-time temporary password (relayed manually, consistent with PRD §8's manual-notification model in v1.0) and sets `force_password_change=true` |
| `PUT` | `/api/v1/towers/{tower_id}/association-members/{member_id}` | `{ name?, phone?, role_id? }` | same |
| `POST` | `/api/v1/towers/{tower_id}/association-members/{member_id}/deactivate` | — | same; `409 LAST_ADMIN` if this is the tower's only active `Admin`-role member |
| `GET` | `/api/v1/towers/{tower_id}/audit-log?page=&page_size=&entity_type=&from=&to=` | — | `require_permission("VIEW_REPORTS")` — read-only endpoint consumed by Module 5's activity feed |

## Pydantic schemas (request/response), representative subset

```python
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    user: UserOut
    permissions: list[str]
    towers: list[TowerMembership]

class TowerMembership(BaseModel):
    tower_id: UUID
    tower_name: str
    role_name: str

class CreateAssociationMemberRequest(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    phone: str = Field(pattern=r"^[6-9]\d{9}$")
    role_id: UUID

class CreateAssociationMemberResponse(BaseModel):
    association_member: AssociationMemberOut
    temporary_password: str  # shown once; not retrievable again

class CreateRoleRequest(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    permission_codes: list[str] = Field(min_length=1)

class AuditLogEntryOut(BaseModel):
    id: UUID
    tower_id: UUID | None
    user_id: UUID | None
    actor_label: str
    action: str
    entity_type: str
    entity_id: UUID
    before: dict | None
    after: dict | None
    created_at: datetime
```

## SQLAlchemy table definitions

All `id` columns are `UUID(as_uuid=True) primary_key, server_default=text("gen_random_uuid()")` —
pgcrypto's `gen_random_uuid()` is available natively on Postgres 16/RDS; this is a Module-1
convention every other module should reuse for consistency:

```python
class User(Base):
    __tablename__ = "users"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    account_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'tower_admin' | 'flat_owner'
    is_superuser: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    force_password_change: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_login_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)  # sha256 hex
    user_agent: Mapped[str | None] = mapped_column(String(255))
    ip_address: Mapped[str | None] = mapped_column(String(45))
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

class Permission(Base):
    __tablename__ = "permissions"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)  # e.g. 'RECORD_PAYMENT'
    description: Mapped[str] = mapped_column(String(255), nullable=False)

class Role(Base):
    __tablename__ = "roles"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    tower_id: Mapped[UUID] = mapped_column(ForeignKey("towers.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    is_system_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    deactivated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("tower_id", "name", name="uq_role_tower_name"),)

class RolePermission(Base):
    __tablename__ = "role_permissions"
    role_id: Mapped[UUID] = mapped_column(ForeignKey("roles.id"), primary_key=True)
    permission_id: Mapped[UUID] = mapped_column(ForeignKey("permissions.id"), primary_key=True)

class AssociationMember(Base):
    __tablename__ = "association_members"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    tower_id: Mapped[UUID] = mapped_column(ForeignKey("towers.id"), nullable=False, index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    role_id: Mapped[UUID] = mapped_column(ForeignKey("roles.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone: Mapped[str] = mapped_column(String(15), nullable=False)
    deactivated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("tower_id", "user_id", name="uq_member_tower_user"),)

class ApartmentComplex(Base):
    __tablename__ = "apartment_complexes"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

class Tower(Base):
    __tablename__ = "towers"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    complex_id: Mapped[UUID] = mapped_column(ForeignKey("apartment_complexes.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)  # short uppercase code (e.g. "OAK", "SUN2"), auto-derived from `name` at creation (superuser can override before save); used by Module 3's receipt numbering (`{tower_code}-{year}-{seq:06d}`, see ../03-maintenance-billing/backend.md §1.6) — this is the only reason this column exists
    total_floors: Mapped[int] = mapped_column(Integer, nullable=False)
    total_flats: Mapped[int] = mapped_column(Integer, nullable=False)
    association_name: Mapped[str] = mapped_column(String(200), nullable=False)
    deactivated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    tower_id: Mapped[UUID | None] = mapped_column(ForeignKey("towers.id"), index=True)  # nullable: complex-level actions have no tower
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))  # nullable: system-generated entries (e.g. auto-overdue transition)
    actor_label: Mapped[str] = mapped_column(String(150), nullable=False)  # snapshot of actor name/email at write time
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. 'ROLE_PERMISSIONS_UPDATED'
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(nullable=False)
    before: Mapped[dict | None] = mapped_column(JSONB)
    after: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), index=True)
```

Note: `audit_log` here adds two columns beyond the literal list in
`../00-architecture-and-standards.md` §6 (`tower_id, user_id, action, entity_type, entity_id,
before, after, created_at`): `actor_label` (a name/email snapshot so the audit trail stays
readable even after a `User`/`AssociationMember` is later renamed or deactivated) and a
nullable `tower_id`/`user_id` (to allow complex-level and system-generated entries). **Flag
for the architecture doc owner**: confirm these two additions are acceptable, or fold them
into the `00` doc's canonical column list so Modules 3/4 build against the same shape (see
[`overview.md`](./overview.md) "Open questions").

## The shared audit-log write helper (used directly by this module, imported by 3/4)

```python
async def write_audit_log(
    db: AsyncSession,
    *,
    actor: User,
    tower_id: UUID | None,
    action: str,
    entity_type: str,
    entity_id: UUID,
    before: dict | None,
    after: dict | None,
) -> None:
    db.add(AuditLog(
        tower_id=tower_id,
        user_id=actor.id,
        actor_label=actor.email,          # or association_member.name if available
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before=before,
        after=after,
    ))
    # caller commits as part of the same transaction as the entity write —
    # audit row and entity change must be atomic (see Acceptance Criteria in overview.md).
```

## `require_permission()` dependency — how it works

Pseudocode; every module's routers depend on this, never on ad-hoc `if user.role == ...` checks:

```python
def require_permission(permission_code: str):
    async def dependency(
        tower_id: UUID = Path(...),                 # path param on every tower-scoped route
        current_user: User = Depends(get_current_user),  # decodes JWT from httpOnly cookie
        db: AsyncSession = Depends(get_db),
    ) -> AssociationMember:
        if current_user.is_superuser:
            return None  # superuser bypasses tower RBAC entirely (platform ops only)

        member = await db.scalar(
            select(AssociationMember)
            .where(
                AssociationMember.user_id == current_user.id,
                AssociationMember.tower_id == tower_id,      # <- the tower isolation check
                AssociationMember.deactivated_at.is_(None),
            )
            .options(joinedload(AssociationMember.role).joinedload(Role.permissions))
        )
        if member is None:
            # user has no membership in THIS tower at all — covers both
            # "no role assigned" and "cross-tower access attempt"
            raise HTTPException(403, detail={"error_code": "TOWER_ACCESS_DENIED", ...})

        if member.role.deactivated_at is not None:
            raise HTTPException(403, detail={"error_code": "ROLE_INACTIVE", ...})

        granted_codes = {p.code for p in member.role.permissions}
        if permission_code not in granted_codes:
            raise HTTPException(403, detail={"error_code": "PERMISSION_DENIED", ...})

        tower = await db.get(Tower, tower_id)
        if tower.deactivated_at is not None and _is_mutating_request():
            raise HTTPException(409, detail={"error_code": "TOWER_INACTIVE", ...})

        return member
    return dependency
```

Key properties every module owner should rely on: (1) it re-derives tower access from the
`AssociationMember` row on **every request** — it never trusts a `tower_id` in the JWT or
request body alone; (2) a missing membership and a wrong-tower membership both collapse to
the same `403 TOWER_ACCESS_DENIED` (no `404` — do not leak whether a tower exists to a
caller who isn't a member of it); (3) flat owners use a parallel
`require_flat_owner_access(flat_id)` dependency built in Module 2 (implicit
`VIEW_TOWER_DATA` + `MANAGE_OWN_FLAT`, no `AssociationMember` row) — Module 1 exposes the
permission-check primitives Module 2 composes over.

## Backend test plan

**Unit:**

- `require_permission("CREATE_BILLING_CYCLE")` denies a user whose role lacks that
  permission with `403 PERMISSION_DENIED`, and allows a user whose role includes it.
- `require_permission()` returns `403 TOWER_ACCESS_DENIED` (not `404`, not `500`) for a user
  with zero `AssociationMember` rows anywhere in the system.
- `require_permission()` bypasses all tower/role checks when `current_user.is_superuser`
  is `True`.
- `require_permission()` rejects (`409 TOWER_INACTIVE`) a mutating call against a
  deactivated tower but allows a read-only (`GET`) call against the same tower.
- Password hashing: `argon2id` verify succeeds for correct password, fails for incorrect,
  and a changed hash never matches the plaintext via string equality (guards against a
  regression to plaintext/naive hashing).
- Refresh token rotation: reusing an already-rotated (single-use) refresh token revokes the
  entire token family for that user and returns `401` on the reuse attempt itself.
- Role deletion guard: attempting to deactivate a role with `is_system_default=True`
  raises `409 ROLE_IMMUTABLE` before any DB write.
- Last-admin guard: deactivating an `AssociationMember` computes "is this the tower's only
  active Admin-role member" correctly when there are 0, 1, and 2+ other active admins.

**Integration (DB + HTTP, real Postgres via test container):**

- Tower admin from Tower A cannot `GET /api/v1/towers/{B}/flats` (routed through Module 2,
  but the guard is this module's) even with a fully valid, unexpired token for Tower A.
- `audit_log` row is created with correct `before`/`after` JSON on a `role_permissions`
  change (`PUT /api/v1/towers/{tower_id}/roles/{role_id}`) — assert `before` reflects the
  pre-change permission code set and `after` the post-change set.
- Creating an association member with an email that already exists as a flat-owner `User`
  links the existing `User` row (no duplicate `users` row, `AssociationMember.user_id`
  points at the pre-existing id).
- `POST /api/v1/towers/{tower_id}/deactivate` returns `409 TOWER_HAS_ACTIVE_FINANCIALS` when
  an `Overdue` due exists, and succeeds (`200`, `deactivated_at` set) once all dues are
  `Paid`.
- `POST /api/v1/auth/login` with a wrong password 5 times in a row does not leak timing
  differences that would distinguish "wrong password" from "no such user" (basic
  constant-time comparison check, not full rate-limiting — rate-limiting is a WAF concern
  per `../06-cloud-devops.md`).
- Full login → refresh → logout cycle: cookies set on login, refresh rotates them and
  invalidates the old refresh token row (`revoked_at` set), logout clears cookies and
  revokes the current token.
- Complex/tower bootstrap: `POST /api/v1/complexes` then
  `POST /api/v1/complexes/{id}/towers` as a superuser creates a `Tower` with a seeded
  `Admin` role holding all 11 permissions from the catalog, and a non-superuser (even one
  with every tower-level permission somewhere else) gets `403` on both endpoints.

**What must NOT break (regression guardrails):**

- The `require_permission()` re-validation of `tower_id` against the caller's actual
  membership must never be short-circuited by trusting a `tower_id` embedded in the JWT —
  any future optimization that caches permissions in the token must still re-check tower
  membership per request.
- No endpoint in this module ever hard-deletes a row (`DELETE` is not implemented anywhere
  in this module's routers) — only `deactivated_at`/soft-delete transitions.
- The system-default `Admin` role can never end up with zero permissions or be deactivated
  — both must remain structurally impossible (DB constraint or app-level guard,
  belt-and-suspenders).
- Every write that changes `role_permissions`, `Tower`, or `AssociationMember` must produce
  exactly one `audit_log` row in the same transaction — a schema/refactor change to these
  tables must not silently drop the audit call.
- Cross-tower isolation must hold under pagination too — `GET
  /api/v1/towers/{tower_id}/association-members` must never return rows belonging to a
  different `tower_id`, even via a crafted `page`/`page_size` or filter query param.
