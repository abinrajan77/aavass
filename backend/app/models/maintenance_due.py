"""Per-flat maintenance due (backend.md §1.4). `amount`, `assigned_to_*`, and `due_date` are
frozen at generation time and never updated by any endpoint afterward — only `status`
transitions (`pending -> overdue`, `pending/overdue -> paid`). See backend.md §8.3 regression
list.

`tower_id` is denormalized from `billing_cycle_id` at insert time (not derived via a join) so
list/dashboard queries can filter by tower directly, per the 200ms/400ms list-query and
250ms/500ms dashboard-aggregate budgets in `00-architecture-and-standards.md` §4.
"""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    TIMESTAMP,
    Date,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base_class import Base


class MaintenanceDue(Base):
    __tablename__ = "maintenance_dues"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    billing_cycle_id: Mapped[UUID] = mapped_column(
        ForeignKey("billing_cycles.id"), nullable=False, index=True
    )
    tower_id: Mapped[UUID] = mapped_column(ForeignKey("towers.id"), nullable=False, index=True)
    flat_id: Mapped[UUID] = mapped_column(ForeignKey("flats.id"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    carpet_area_snapshot: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    # 'tenant' | 'owner'
    assigned_to_type: Mapped[str] = mapped_column(String(10), nullable=False)
    # tenant.id or owner.id depending on assigned_to_type; frozen at generation, never re-derived.
    assigned_to_id: Mapped[UUID] = mapped_column(nullable=False)
    assigned_to_name_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    primary_owner_id_snapshot: Mapped[UUID] = mapped_column(
        ForeignKey("owners.id"), nullable=False
    )
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    # 'pending' | 'paid' | 'overdue'
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("billing_cycle_id", "flat_id", name="uq_due_cycle_flat"),
        Index("ix_maintenance_dues_tower_status_due_date", "tower_id", "status", "due_date"),
    )
