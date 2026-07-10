"""A billing cycle snapshots the formula/grace-period version in effect at generation time
(backend.md §1.3). `UNIQUE(tower_id, month, year)` is the DB-level idempotency guarantee for
cycle generation — never drop or weaken this constraint (see backend.md §8.3 regression list).

Immutability: once at least one `maintenance_dues` row exists for a cycle, `PUT`/`DELETE`
return `409 IMMUTABLE_RECORD` (enforced in the router/service layer, not by a DB trigger).
"""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    TIMESTAMP,
    Date,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base_class import Base


class BillingCycle(Base):
    __tablename__ = "billing_cycles"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    tower_id: Mapped[UUID] = mapped_column(ForeignKey("towers.id"), nullable=False, index=True)
    month: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    formula_id: Mapped[UUID] = mapped_column(
        ForeignKey("maintenance_formulas.id"), nullable=False
    )
    grace_period_days_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    # 'generating' | 'active'
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="generating")
    # Set when generation is async (backend.md §4); FK to the generic `jobs` table.
    job_id: Mapped[UUID | None] = mapped_column(ForeignKey("jobs.id"), nullable=True)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("association_members.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("tower_id", "month", "year", name="uq_billing_cycle_tower_month_year"),
    )
