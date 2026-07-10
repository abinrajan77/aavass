"""Shared payment table (backend.md §1.5) — also used by Module 4 for special-collection
payments via the `due_type` discriminator. There is no separate `special_collection_payments`
table; do not create one (`00-architecture-and-standards.md` §7)."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import TIMESTAMP, Date, ForeignKey, Numeric, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base_class import Base


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    tower_id: Mapped[UUID] = mapped_column(ForeignKey("towers.id"), nullable=False, index=True)
    # 'maintenance' | 'special_collection'
    due_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # Polymorphic: maintenance_dues.id or (Module 4's) special_collection_dues.id — no DB-level
    # FK, existence/ownership validated in the service layer (`record_payment`).
    due_id: Mapped[UUID] = mapped_column(nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount_received: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    # 'cash' | 'bank_transfer' | 'cheque'
    payment_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    reference_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    recorded_by: Mapped[UUID] = mapped_column(ForeignKey("association_members.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    __table_args__ = (UniqueConstraint("due_type", "due_id", name="uq_payment_due"),)
