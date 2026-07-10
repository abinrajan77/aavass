"""Versioned, insert-only grace-period config (backend.md §1.2). Same append-only pattern as
`MaintenanceFormula` — every tower gets a seed row (`grace_period_days=0`) when the tower is
created; that seeding is Module 1's responsibility (FK-only dependency here)."""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import TIMESTAMP, Date, ForeignKey, Integer, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base_class import Base


class GracePeriodConfig(Base):
    __tablename__ = "grace_period_configs"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    tower_id: Mapped[UUID] = mapped_column(ForeignKey("towers.id"), nullable=False, index=True)
    grace_period_days: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("association_members.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "tower_id", "effective_from", name="uq_grace_period_tower_effective_from"
        ),
    )
