"""special collections, special collection dues, expenditures

Revision ID: f1c3a8f2b6d1
Revises: 85b94fc0f4bc
Create Date: 2026-07-10 15:00:00.000000

Module 4 (Special Collections & Expenditure) tables, per
`specs/04-special-collections-expenditure/backend.md`. `special_collection_dues.flat_id`/
`.owner_id` are plain `UUID NOT NULL` columns with **no DB-level foreign key** to
`flats`/`owners` — Module 2 doesn't exist in this codebase yet (see
`app/models/special_collection_due.py` docstring and `app/services/flat_directory.py`).
`flat_number`/`owner_name` are an addition beyond the literal spec table, snapshotting
Module 2 display data at due-generation time in the absence of Module 2 tables to join
against.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1c3a8f2b6d1"
down_revision: str | None = "85b94fc0f4bc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "special_collections",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tower_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("total_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column(
            "split_basis", sa.String(length=20), server_default=sa.text("'equal'"), nullable=False
        ),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("dues_generated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("skipped_flats", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deactivated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint(
            "total_amount > 0", name="ck_special_collections_total_amount_positive"
        ),
        sa.CheckConstraint(
            "split_basis = 'equal'", name="ck_special_collections_split_basis_equal"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["association_members.id"]),
        sa.ForeignKeyConstraint(["tower_id"], ["towers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_special_collections_tower_id"),
        "special_collections",
        ["tower_id"],
        unique=False,
    )

    op.create_table(
        "special_collection_dues",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("special_collection_id", sa.Uuid(), nullable=False),
        sa.Column("tower_id", sa.Uuid(), nullable=False),
        # Module 2 Flat/Owner — no DB FK yet, see module docstring above.
        sa.Column("flat_id", sa.Uuid(), nullable=False),
        sa.Column("flat_number", sa.String(length=20), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("owner_name", sa.String(length=150), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column(
            "status", sa.String(length=20), server_default=sa.text("'pending'"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["special_collection_id"], ["special_collections.id"]),
        sa.ForeignKeyConstraint(["tower_id"], ["towers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "special_collection_id", "flat_id", name="uq_special_collection_dues_collection_flat"
        ),
    )
    op.create_index(
        op.f("ix_special_collection_dues_special_collection_id"),
        "special_collection_dues",
        ["special_collection_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_special_collection_dues_tower_id"),
        "special_collection_dues",
        ["tower_id"],
        unique=False,
    )

    op.create_table(
        "expenditures",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tower_id", sa.Uuid(), nullable=False),
        sa.Column("expenditure_date", sa.Date(), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("vendor_payee_name", sa.String(length=200), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("payment_mode", sa.String(length=20), nullable=False),
        sa.Column("attachment_s3_key", sa.String(length=500), nullable=True),
        sa.Column(
            "is_complex_contribution",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("complex_total_amount", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("recorded_by", sa.Uuid(), nullable=False),
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
        sa.CheckConstraint("amount > 0", name="ck_expenditures_amount_positive"),
        sa.CheckConstraint(
            "complex_total_amount IS NULL OR is_complex_contribution",
            name="ck_expenditures_complex_total_requires_flag",
        ),
        sa.ForeignKeyConstraint(["recorded_by"], ["association_members.id"]),
        sa.ForeignKeyConstraint(["tower_id"], ["towers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_expenditures_tower_id"), "expenditures", ["tower_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_expenditures_tower_id"), table_name="expenditures")
    op.drop_table("expenditures")
    op.drop_index(
        op.f("ix_special_collection_dues_tower_id"), table_name="special_collection_dues"
    )
    op.drop_index(
        op.f("ix_special_collection_dues_special_collection_id"),
        table_name="special_collection_dues",
    )
    op.drop_table("special_collection_dues")
    op.drop_index(op.f("ix_special_collections_tower_id"), table_name="special_collections")
    op.drop_table("special_collections")
