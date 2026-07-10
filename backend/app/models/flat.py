# STUB for Module 2 — owned by 02-flat-owner-tenant, minimal fields only for Module 3's
# FK/read needs.
"""Minimal `Flat` model so Module 3 (Maintenance Billing) has FK integrity and a read surface
(`app.services.flats_service`) to generate billing cycles against, per `specs/02-flat-owner-tenant`
not having landed yet. Only the columns Module 3 actually reads are modeled here — no ownership
history, no CRUD routers, no soft-delete audit trail beyond the bare `is_active` flag. Whoever
implements Module 2 for real should replace this file with the full spec (FlatOwnership,
deactivated_at, etc.) rather than extend it in place.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import TIMESTAMP, Boolean, ForeignKey, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base_class import Base


class Flat(Base):
    __tablename__ = "flats"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    tower_id: Mapped[UUID] = mapped_column(ForeignKey("towers.id"), nullable=False, index=True)
    flat_number: Mapped[str] = mapped_column(String(20), nullable=False)
    carpet_area: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    # 'owner_occupied' | 'tenant_occupied' | 'vacant'
    occupancy_status: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
