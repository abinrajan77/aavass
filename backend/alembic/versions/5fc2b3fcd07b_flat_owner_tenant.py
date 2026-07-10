"""flat owner tenant tables

Revision ID: 5fc2b3fcd07b
Revises: 85b94fc0f4bc
Create Date: 2026-07-10 15:30:00.000000

Module 2 (Flat, Owner & Tenant Management) — creates `flats`, `owners`, `flat_ownerships`,
`tenants`. Per `specs/02-flat-owner-tenant/backend.md` / overview.md's "Data model contract
for downstream modules", two partial unique indexes are the DB-level backstop for this
module's core invariants and must never be dropped/weakened by a future migration:

- `uq_tenant_flat_active` — at most one active tenant per flat.
- `uq_flat_primary_contact_active` — exactly one primary owner per flat while it has any
  currently-active ownership row.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5fc2b3fcd07b"
down_revision: str | None = "85b94fc0f4bc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

flat_type_enum = postgresql.ENUM("1BHK", "2BHK", "3BHK", "OTHER", name="flat_type")
occupancy_status_enum = postgresql.ENUM(
    "owner_occupied", "tenant_occupied", "vacant", name="occupancy_status"
)


def upgrade() -> None:
    bind = op.get_bind()
    flat_type_enum.create(bind, checkfirst=True)
    occupancy_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "flats",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tower_id", sa.Uuid(), nullable=False),
        sa.Column("flat_number", sa.String(length=20), nullable=False),
        sa.Column("floor", sa.Integer(), nullable=False),
        sa.Column(
            "type",
            postgresql.ENUM("1BHK", "2BHK", "3BHK", "OTHER", name="flat_type", create_type=False),
            nullable=False,
        ),
        sa.Column("carpet_area_sqft", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column(
            "occupancy_status",
            postgresql.ENUM(
                "owner_occupied",
                "tenant_occupied",
                "vacant",
                name="occupancy_status",
                create_type=False,
            ),
            server_default="vacant",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deactivated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tower_id"], ["towers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_flats_tower_id"), "flats", ["tower_id"], unique=False)
    op.create_index(
        "uq_flat_tower_number_active",
        "flats",
        ["tower_id", "flat_number"],
        unique=True,
        postgresql_where=sa.text("deactivated_at IS NULL"),
    )

    op.create_table(
        "owners",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("id_number", sa.String(length=50), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deactivated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )

    op.create_table(
        "flat_ownerships",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("flat_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("is_primary_contact", sa.Boolean(), nullable=False),
        sa.Column("date_from", sa.Date(), nullable=False),
        sa.Column("date_to", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["flat_id"], ["flats.id"]),
        sa.ForeignKeyConstraint(["owner_id"], ["owners.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_flat_ownerships_flat_id"), "flat_ownerships", ["flat_id"], unique=False
    )
    op.create_index(
        op.f("ix_flat_ownerships_owner_id"), "flat_ownerships", ["owner_id"], unique=False
    )
    op.create_index(
        "uq_flat_primary_contact_active",
        "flat_ownerships",
        ["flat_id"],
        unique=True,
        postgresql_where=sa.text("date_to IS NULL AND is_primary_contact"),
    )

    op.create_table(
        "tenants",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("flat_id", sa.Uuid(), nullable=False),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("id_number", sa.String(length=50), nullable=True),
        sa.Column("lease_start", sa.Date(), nullable=False),
        sa.Column("lease_end", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("vacated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("vacated_by_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deactivated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["flat_id"], ["flats.id"]),
        sa.ForeignKeyConstraint(["vacated_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tenants_flat_id"), "tenants", ["flat_id"], unique=False)
    op.create_index(
        "uq_tenant_flat_active",
        "tenants",
        ["flat_id"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )


def downgrade() -> None:
    op.drop_index("uq_tenant_flat_active", table_name="tenants")
    op.drop_index(op.f("ix_tenants_flat_id"), table_name="tenants")
    op.drop_table("tenants")

    op.drop_index("uq_flat_primary_contact_active", table_name="flat_ownerships")
    op.drop_index(op.f("ix_flat_ownerships_owner_id"), table_name="flat_ownerships")
    op.drop_index(op.f("ix_flat_ownerships_flat_id"), table_name="flat_ownerships")
    op.drop_table("flat_ownerships")

    op.drop_table("owners")

    op.drop_index("uq_flat_tower_number_active", table_name="flats")
    op.drop_index(op.f("ix_flats_tower_id"), table_name="flats")
    op.drop_table("flats")

    bind = op.get_bind()
    occupancy_status_enum.drop(bind, checkfirst=True)
    flat_type_enum.drop(bind, checkfirst=True)
