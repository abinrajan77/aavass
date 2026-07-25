from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import TIMESTAMP, Date, ForeignKey, Numeric, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base_class import Base


class SpecialCollectionDue(Base):
    """Per `specs/04-special-collections-expenditure/backend.md`. `flat_id`/`owner_id` carry
    real DB-level foreign keys to `flats`/`owners` (Module 2 landed after this module was
    originally built — see `043cebe147d4` for the backfilled constraints).

    `flat_number`/`owner_name` are a deliberate addition beyond the literal spec table: the
    spec's `SpecialCollectionDueOut` schema expects these "joined from Module 2 Flat/Owner
    for display"; they're snapshotted at generation time instead (sourced from the
    `FlatDirectory` seam, `app/services/flat_directory.py`) as a fast, denormalized read
    path — a live join would also work, but no part of this module needs it to change.
    """

    __tablename__ = "special_collection_dues"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    special_collection_id: Mapped[UUID] = mapped_column(
        ForeignKey("special_collections.id"), nullable=False, index=True
    )
    tower_id: Mapped[UUID] = mapped_column(ForeignKey("towers.id"), nullable=False, index=True)
    flat_id: Mapped[UUID] = mapped_column(ForeignKey("flats.id"), nullable=False)
    flat_number: Mapped[str] = mapped_column(String(20), nullable=False)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("owners.id"), nullable=False)
    owner_name: Mapped[str] = mapped_column(String(150), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "special_collection_id", "flat_id", name="uq_special_collection_dues_collection_flat"
        ),
    )
