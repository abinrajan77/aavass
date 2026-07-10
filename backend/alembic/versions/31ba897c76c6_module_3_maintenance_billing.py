"""module 3 maintenance billing

Revision ID: 31ba897c76c6
Revises: 5fc2b3fcd07b
Create Date: 2026-07-10 15:00:00.000000

Adds:
- The shared generic `jobs` table (`06-cloud-devops.md` §4).
- Module 3's own tables: `maintenance_formulas`, `grace_period_configs`, `billing_cycles`,
  `maintenance_dues`, `payments`, `receipts`, `receipt_counters` (backend.md §1).

`flats`/`owners`/`tenants` (referenced here via FK) are created by Module 2's migration
(`5fc2b3fcd07b`), now chained as this migration's parent — this migration originally shipped
its own stub versions of those three tables (see git history), since Module 2 hadn't landed
yet; that stub was removed once Module 2's real tables superseded it.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "31ba897c76c6"
down_revision: str | None = "5fc2b3fcd07b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- Shared generic jobs table (06-cloud-devops.md §4) ---
    op.create_table(
        "jobs",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tower_id", sa.Uuid(), nullable=False),
        sa.Column("job_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("idempotency_key", sa.String(length=200), nullable=True),
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
        sa.ForeignKeyConstraint(["tower_id"], ["towers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_jobs_tower_id"), "jobs", ["tower_id"], unique=False)

    # --- Module 3: maintenance_formulas ---
    op.create_table(
        "maintenance_formulas",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tower_id", sa.Uuid(), nullable=False),
        sa.Column("base_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("per_sqft_rate", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by"], ["association_members.id"]),
        sa.ForeignKeyConstraint(["tower_id"], ["towers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tower_id", "effective_from", name="uq_formula_tower_effective_from"
        ),
    )
    op.create_index(
        op.f("ix_maintenance_formulas_tower_id"), "maintenance_formulas", ["tower_id"], unique=False
    )

    # --- Module 3: grace_period_configs ---
    op.create_table(
        "grace_period_configs",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tower_id", sa.Uuid(), nullable=False),
        sa.Column("grace_period_days", sa.Integer(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by"], ["association_members.id"]),
        sa.ForeignKeyConstraint(["tower_id"], ["towers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tower_id", "effective_from", name="uq_grace_period_tower_effective_from"
        ),
    )
    op.create_index(
        op.f("ix_grace_period_configs_tower_id"), "grace_period_configs", ["tower_id"], unique=False
    )

    # --- Module 3: billing_cycles ---
    op.create_table(
        "billing_cycles",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tower_id", sa.Uuid(), nullable=False),
        sa.Column("month", sa.SmallInteger(), nullable=False),
        sa.Column("year", sa.SmallInteger(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("formula_id", sa.Uuid(), nullable=False),
        sa.Column("grace_period_days_snapshot", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by"], ["association_members.id"]),
        sa.ForeignKeyConstraint(["formula_id"], ["maintenance_formulas.id"]),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
        sa.ForeignKeyConstraint(["tower_id"], ["towers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tower_id", "month", "year", name="uq_billing_cycle_tower_month_year"
        ),
    )
    op.create_index(
        op.f("ix_billing_cycles_tower_id"), "billing_cycles", ["tower_id"], unique=False
    )

    # --- Module 3: maintenance_dues ---
    op.create_table(
        "maintenance_dues",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("billing_cycle_id", sa.Uuid(), nullable=False),
        sa.Column("tower_id", sa.Uuid(), nullable=False),
        sa.Column("flat_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("carpet_area_snapshot", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("assigned_to_type", sa.String(length=10), nullable=False),
        sa.Column("assigned_to_id", sa.Uuid(), nullable=False),
        sa.Column("assigned_to_name_snapshot", sa.String(length=200), nullable=False),
        sa.Column("primary_owner_id_snapshot", sa.Uuid(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["billing_cycle_id"], ["billing_cycles.id"]),
        sa.ForeignKeyConstraint(["flat_id"], ["flats.id"]),
        sa.ForeignKeyConstraint(["primary_owner_id_snapshot"], ["owners.id"]),
        sa.ForeignKeyConstraint(["tower_id"], ["towers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("billing_cycle_id", "flat_id", name="uq_due_cycle_flat"),
    )
    op.create_index(
        op.f("ix_maintenance_dues_billing_cycle_id"), "maintenance_dues", ["billing_cycle_id"], unique=False
    )
    op.create_index(
        op.f("ix_maintenance_dues_flat_id"), "maintenance_dues", ["flat_id"], unique=False
    )
    op.create_index(
        op.f("ix_maintenance_dues_tower_id"), "maintenance_dues", ["tower_id"], unique=False
    )
    op.create_index(
        "ix_maintenance_dues_tower_status_due_date",
        "maintenance_dues",
        ["tower_id", "status", "due_date"],
        unique=False,
    )

    # --- Shared: payments ---
    op.create_table(
        "payments",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tower_id", sa.Uuid(), nullable=False),
        sa.Column("due_type", sa.String(length=20), nullable=False),
        sa.Column("due_id", sa.Uuid(), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("amount_received", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("payment_mode", sa.String(length=20), nullable=False),
        sa.Column("reference_number", sa.String(length=100), nullable=True),
        sa.Column("recorded_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["recorded_by"], ["association_members.id"]),
        sa.ForeignKeyConstraint(["tower_id"], ["towers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("due_type", "due_id", name="uq_payment_due"),
    )
    op.create_index(op.f("ix_payments_tower_id"), "payments", ["tower_id"], unique=False)

    # --- Shared: receipts ---
    op.create_table(
        "receipts",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tower_id", sa.Uuid(), nullable=False),
        sa.Column("due_type", sa.String(length=20), nullable=False),
        sa.Column("due_id", sa.Uuid(), nullable=False),
        sa.Column("payment_id", sa.Uuid(), nullable=False),
        sa.Column("receipt_number", sa.String(length=30), nullable=False),
        sa.Column("owner_name_snapshot", sa.String(length=200), nullable=False),
        sa.Column("billing_period_label", sa.String(length=100), nullable=False),
        sa.Column("pdf_s3_key", sa.String(length=300), nullable=False),
        sa.Column(
            "generated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"]),
        sa.ForeignKeyConstraint(["tower_id"], ["towers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payment_id"),
        sa.UniqueConstraint("receipt_number"),
        sa.UniqueConstraint("due_type", "due_id", name="uq_receipt_due"),
    )
    op.create_index(op.f("ix_receipts_tower_id"), "receipts", ["tower_id"], unique=False)

    # --- Shared: receipt_counters ---
    op.create_table(
        "receipt_counters",
        sa.Column("tower_id", sa.Uuid(), nullable=False),
        sa.Column(
            "next_number", sa.Integer(), server_default=sa.text("1"), nullable=False
        ),
        sa.ForeignKeyConstraint(["tower_id"], ["towers.id"]),
        sa.PrimaryKeyConstraint("tower_id"),
    )


def downgrade() -> None:
    op.drop_table("receipt_counters")
    op.drop_index(op.f("ix_receipts_tower_id"), table_name="receipts")
    op.drop_table("receipts")
    op.drop_index(op.f("ix_payments_tower_id"), table_name="payments")
    op.drop_table("payments")
    op.drop_index("ix_maintenance_dues_tower_status_due_date", table_name="maintenance_dues")
    op.drop_index(op.f("ix_maintenance_dues_tower_id"), table_name="maintenance_dues")
    op.drop_index(op.f("ix_maintenance_dues_flat_id"), table_name="maintenance_dues")
    op.drop_index(op.f("ix_maintenance_dues_billing_cycle_id"), table_name="maintenance_dues")
    op.drop_table("maintenance_dues")
    op.drop_index(op.f("ix_billing_cycles_tower_id"), table_name="billing_cycles")
    op.drop_table("billing_cycles")
    op.drop_index(op.f("ix_grace_period_configs_tower_id"), table_name="grace_period_configs")
    op.drop_table("grace_period_configs")
    op.drop_index(op.f("ix_maintenance_formulas_tower_id"), table_name="maintenance_formulas")
    op.drop_table("maintenance_formulas")
    op.drop_index(op.f("ix_jobs_tower_id"), table_name="jobs")
    op.drop_table("jobs")
