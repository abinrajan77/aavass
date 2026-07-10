from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import TIMESTAMP, CheckConstraint, Date, ForeignKey, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base_class import Base


class SpecialCollection(Base):
    """Per `specs/04-special-collections-expenditure/backend.md`. Immutable once created —
    dues are always generated synchronously at creation time in this slice (no draft state,
    no PUT/PATCH route), mirroring billing-cycle immutability. `deactivated_at` doubles as
    the "cancelled" flag (only allowed pre-payment, enforced in the router, not here)."""

    __tablename__ = "special_collections"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    tower_id: Mapped[UUID] = mapped_column(ForeignKey("towers.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    # widened to an enum in a future version — see backend.md; only 'equal' exists in v1.0
    split_basis: Mapped[str] = mapped_column(String(20), nullable=False, server_default="equal")
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    # NULL only during the brief async-job window (not exercised in this slice — dues are
    # always generated synchronously here, so this is set in the same transaction as the row).
    dues_generated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    # [{flat_id, flat_number, reason}] snapshot from generation, for admin visibility.
    skipped_flats: Mapped[list | None] = mapped_column(JSONB)
    created_by: Mapped[UUID] = mapped_column(
        ForeignKey("association_members.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    # soft-delete/cancel; only allowed pre-generation or if zero dues paid (enforced in router)
    deactivated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    __table_args__ = (
        CheckConstraint("total_amount > 0", name="ck_special_collections_total_amount_positive"),
        CheckConstraint(
            "split_basis = 'equal'", name="ck_special_collections_split_basis_equal"
        ),
    )
