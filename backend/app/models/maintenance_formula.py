"""Versioned, insert-only maintenance formula (backend.md §1.1). A "change" is always a new
row — no `UPDATE`/`DELETE` is ever issued against this table by any endpoint."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import TIMESTAMP, Date, ForeignKey, Numeric, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base_class import Base


class MaintenanceFormula(Base):
    __tablename__ = "maintenance_formulas"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    tower_id: Mapped[UUID] = mapped_column(ForeignKey("towers.id"), nullable=False, index=True)
    base_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    per_sqft_rate: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("association_members.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("tower_id", "effective_from", name="uq_formula_tower_effective_from"),
    )
