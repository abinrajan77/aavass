"""special collection dues flat/owner FKs and special_collections.job_id

Revision ID: 043cebe147d4
Revises: 65fb1510b01d
Create Date: 2026-07-25 22:09:17.872230

`special_collection_dues.flat_id`/`.owner_id` were left FK-less because Module 4 was
originally built before Module 2 (Flat/Owner/Tenant) landed in this codebase (see
`f1c3a8f2b6d1`'s docstring). Module 2 has since landed, so this backfills the same
`flats`/`owners` foreign keys `maintenance_dues` already has.

Also adds `special_collections.job_id` (nullable FK to `jobs.id`), mirroring
`billing_cycles.job_id` — needed for the `>300`-active-flats async due-generation path
(`app.services.special_collection.process_special_collection_job`).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "043cebe147d4"
down_revision: str | None = "65fb1510b01d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_foreign_key(
        "fk_special_collection_dues_flat_id_flats",
        "special_collection_dues",
        "flats",
        ["flat_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_special_collection_dues_owner_id_owners",
        "special_collection_dues",
        "owners",
        ["owner_id"],
        ["id"],
    )
    op.add_column("special_collections", sa.Column("job_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_special_collections_job_id_jobs", "special_collections", "jobs", ["job_id"], ["id"]
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_special_collections_job_id_jobs", "special_collections", type_="foreignkey"
    )
    op.drop_column("special_collections", "job_id")
    op.drop_constraint(
        "fk_special_collection_dues_owner_id_owners",
        "special_collection_dues",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_special_collection_dues_flat_id_flats", "special_collection_dues", type_="foreignkey"
    )
