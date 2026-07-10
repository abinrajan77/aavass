from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base_class import Base


class Expenditure(Base):
    """Per `specs/04-special-collections-expenditure/backend.md` "Design decision: complex-
    level contribution modeled as a flagged Expenditure" — one table for both regular
    expenditures and complex-wide-contribution rows, distinguished by
    `is_complex_contribution`. `amount` is always the figure posted to *this tower's* books;
    `complex_total_amount` is reference-only and must never be summed in reports."""

    __tablename__ = "expenditures"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    tower_id: Mapped[UUID] = mapped_column(ForeignKey("towers.id"), nullable=False, index=True)
    expenditure_date: Mapped[date] = mapped_column(Date, nullable=False)
    category: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # 'cleaning'|'security'|'repairs'|'utilities'|'other'
    description: Mapped[str] = mapped_column(Text, nullable=False)
    vendor_payee_name: Mapped[str] = mapped_column(String(200), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_mode: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # 'cash'|'bank_transfer'|'cheque'
    attachment_s3_key: Mapped[str | None] = mapped_column(String(500))
    is_complex_contribution: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    complex_total_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    recorded_by: Mapped[UUID] = mapped_column(
        ForeignKey("association_members.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deactivated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_expenditures_amount_positive"),
        CheckConstraint(
            "complex_total_amount IS NULL OR is_complex_contribution",
            name="ck_expenditures_complex_total_requires_flag",
        ),
    )
