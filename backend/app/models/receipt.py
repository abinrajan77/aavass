"""Shared receipt table (backend.md §1.6) — also used by Module 4. `receipt_number` is
sequential per tower, shared across `due_type` (one numbering sequence per tower, not one per
due type) — see `app.models.receipt_counter` and `app.services.receipts.next_receipt_number`."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import TIMESTAMP, ForeignKey, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base_class import Base


class Receipt(Base):
    __tablename__ = "receipts"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    tower_id: Mapped[UUID] = mapped_column(ForeignKey("towers.id"), nullable=False, index=True)
    # 'maintenance' | 'special_collection' — denormalized copy from `payments`.
    due_type: Mapped[str] = mapped_column(String(20), nullable=False)
    due_id: Mapped[UUID] = mapped_column(nullable=False)
    payment_id: Mapped[UUID] = mapped_column(
        ForeignKey("payments.id"), nullable=False, unique=True
    )
    # Format `{tower_code}-{year}-{seq:06d}`.
    receipt_number: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    owner_name_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    billing_period_label: Mapped[str] = mapped_column(String(100), nullable=False)
    pdf_s3_key: Mapped[str] = mapped_column(String(300), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    __table_args__ = (UniqueConstraint("due_type", "due_id", name="uq_receipt_due"),)
