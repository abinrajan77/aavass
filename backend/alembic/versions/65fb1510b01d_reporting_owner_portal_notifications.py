"""reporting, owner portal & notifications

Revision ID: 65fb1510b01d
Revises: f1c3a8f2b6d1
Create Date: 2026-07-11 00:00:00.000000

Module 5 (Reporting, Flat Owner Self-Service Portal & Notifications) tables, per
`specs/05-reporting-owner-portal-notifications/backend.md` §1. This module owns exactly two
small tables — everything else it reads (`maintenance_dues`, `payments`, `receipts`,
`special_collection_dues`, `expenditures`, `flats`, `owners`, `flat_ownerships`, `tenants`) is
read-only input owned by Modules 1-4.

`notification_templates` is seeded here with one row per `(event_type, recipient_role)`
combination (`channel='generic'`) — 3 event types x 2 recipient roles = 6 rows. v1.0 has no
admin-editable template screen; the table shape supports adding one later without a schema
change (see `app/models/notification_template.py`).

The seed list below is kept as an inline literal (not imported from
`app.core.notification_templates.NOTIFICATION_TEMPLATE_SEED`), mirroring
`85b94fc0f4bc_seed_permission_catalog.py`'s own precedent/rationale: "Alembic migrations can't
import mutable app state safely across future schema changes." `app.core.notification_templates`
still exists as the single source the *test suite* seeds from (since `tests/conftest.py` builds
schema via `Base.metadata.create_all`, not by running migrations, and therefore needs its own
seeding step) — kept in sync with this file manually, exactly like the permission catalog.

`export_jobs.id` has no server-side default: the application mints this id explicitly so it can
double as the shared `jobs.id` row created in the same request (see
`app/services/export.py::get_or_create_export_job` for the reconciliation rationale) — the
frontend always polls the one canonical `GET /api/v1/towers/{tower_id}/jobs/{job_id}` route
regardless of job type, per `06-cloud-devops.md` §4 and this module's `cloud.md`.
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "65fb1510b01d"
down_revision: str | None = "f1c3a8f2b6d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# One row per (event_type, recipient_role) combination, channel='generic' (v1.0 only channel).
# Kept in sync with `app.core.notification_templates.NOTIFICATION_TEMPLATE_SEED` manually.
_SEED_TEMPLATES: list[tuple[str, str, str]] = [
    (
        "due_generated",
        "resident",
        "Dear {resident_name}, your maintenance due of Rs. {amount} for {flat_number}, "
        "{tower_name} for {period} is due on {due_date}.",
    ),
    (
        "due_generated",
        "owner_copy",
        "Dear Owner, a maintenance due of Rs. {amount} for {flat_number}, {tower_name} for "
        "{period} (resident: {resident_name}) is due on {due_date}. This is a copy for your "
        "records.",
    ),
    (
        "overdue_reminder",
        "resident",
        "Dear {resident_name}, your maintenance payment of Rs. {amount} for {flat_number}, "
        "{tower_name} for {period} was due on {due_date} and is now overdue. Please pay at "
        "the earliest to avoid further delay.",
    ),
    (
        "overdue_reminder",
        "owner_copy",
        "Dear Owner, the maintenance payment of Rs. {amount} for {flat_number}, {tower_name} "
        "for {period} (resident: {resident_name}) was due on {due_date} and is now overdue.",
    ),
    (
        "payment_confirmed",
        "resident",
        "Dear {resident_name}, we have received your payment of Rs. {amount} for "
        "{flat_number}, {tower_name} for {period}. Thank you!",
    ),
    (
        "payment_confirmed",
        "owner_copy",
        "Dear Owner, a payment of Rs. {amount} for {flat_number}, {tower_name} for {period} "
        "(resident: {resident_name}) has been received. This is a copy for your records.",
    ),
]


def upgrade() -> None:
    op.create_table(
        "notification_templates",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("event_type", sa.String(length=30), nullable=False),
        sa.Column("recipient_role", sa.String(length=20), nullable=False),
        sa.Column(
            "channel", sa.String(length=20), server_default=sa.text("'generic'"), nullable=False
        ),
        sa.Column("template_text", sa.Text(), nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False
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
        sa.CheckConstraint(
            "event_type IN ('due_generated', 'overdue_reminder', 'payment_confirmed')",
            name="ck_notification_templates_event_type",
        ),
        sa.CheckConstraint(
            "recipient_role IN ('resident', 'owner_copy')",
            name="ck_notification_templates_recipient_role",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "event_type", "recipient_role", "channel", name="uq_notification_template_key"
        ),
    )

    op.create_table(
        "export_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tower_id", sa.Uuid(), nullable=False),
        sa.Column("report_type", sa.String(length=40), nullable=False),
        sa.Column("format", sa.String(length=10), nullable=False),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "status", sa.String(length=20), server_default=sa.text("'pending'"), nullable=False
        ),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("file_s3_key", sa.String(length=300), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("requested_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint(
            "report_type IN ('collection', 'outstanding_dues', 'expenditure', "
            "'collection_vs_expenditure', 'tenant_register')",
            name="ck_export_jobs_report_type",
        ),
        sa.CheckConstraint("format IN ('pdf', 'csv')", name="ck_export_jobs_format"),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'done', 'failed')",
            name="ck_export_jobs_status",
        ),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["tower_id"], ["towers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_export_jobs_tower_id"), "export_jobs", ["tower_id"], unique=False
    )
    op.create_index(
        "ix_export_jobs_tower_status", "export_jobs", ["tower_id", "status"], unique=False
    )

    notification_templates = sa.table(
        "notification_templates",
        sa.column("id", sa.Uuid()),
        sa.column("event_type", sa.String()),
        sa.column("recipient_role", sa.String()),
        sa.column("channel", sa.String()),
        sa.column("template_text", sa.Text()),
    )
    op.bulk_insert(
        notification_templates,
        [
            {
                "id": uuid.uuid4(),
                "event_type": event_type,
                "recipient_role": recipient_role,
                "channel": "generic",
                "template_text": template_text,
            }
            for event_type, recipient_role, template_text in _SEED_TEMPLATES
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_export_jobs_tower_status", table_name="export_jobs")
    op.drop_index(op.f("ix_export_jobs_tower_id"), table_name="export_jobs")
    op.drop_table("export_jobs")
    op.drop_table("notification_templates")
