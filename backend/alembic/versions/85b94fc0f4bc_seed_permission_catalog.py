"""seed permission catalog

Revision ID: 85b94fc0f4bc
Revises: 2234a93fa075
Create Date: 2026-07-10 14:34:33.987850

Seeds the 11 permissions from `specs/00-architecture-and-standards.md` §5.1. This is the
single authoritative seed; `app.core.permissions.PERMISSION_CATALOG` is the same list used
at runtime (e.g. to seed a tower's Admin role) — kept in sync manually since Alembic
migrations can't import mutable app state safely across future schema changes.
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import column, table
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "85b94fc0f4bc"
down_revision: str | None = "2234a93fa075"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSION_CATALOG: list[tuple[str, str]] = [
    ("MANAGE_COMPLEX", "Create/edit complex & tower records"),
    ("MANAGE_ASSOCIATION_MEMBERS", "Add/edit association members, assign roles"),
    ("MANAGE_RESIDENTS", "Add/edit flats, owners, tenants"),
    ("CONFIGURE_BILLING", "Edit maintenance formula & grace period"),
    ("CREATE_BILLING_CYCLE", "Generate a billing cycle"),
    ("RECORD_PAYMENT", "Mark dues paid, generate receipts"),
    ("MANAGE_SPECIAL_COLLECTIONS", "Create/edit special collections"),
    ("MANAGE_EXPENDITURE", "Record tower/complex expenditure"),
    ("VIEW_REPORTS", "Generate/export reports"),
    ("VIEW_TOWER_DATA", "Read-only tower-wide visibility (flat owners get this by default)"),
    ("MANAGE_OWN_FLAT", "Flat owner: edit own contact/tenant/occupancy details"),
]

permissions_table = table(
    "permissions",
    column("id", postgresql.UUID(as_uuid=True)),
    column("code", sa.String),
    column("description", sa.String),
)


def upgrade() -> None:
    op.bulk_insert(
        permissions_table,
        [
            {"id": uuid.uuid4(), "code": code, "description": description}
            for code, description in PERMISSION_CATALOG
        ],
    )


def downgrade() -> None:
    codes = [code for code, _ in PERMISSION_CATALOG]
    op.execute(permissions_table.delete().where(permissions_table.c.code.in_(codes)))
