# STUB for Module 2 — owned by 02-flat-owner-tenant, minimal fields only for Module 3's
# FK/read needs.
"""See `app/models/flat.py`'s module docstring for the rationale. No lease dates, no tenant
history table — `is_active` is the only lifecycle signal Module 3 needs to find "the current
tenant" of a flat."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import TIMESTAMP, Boolean, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base_class import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    flat_id: Mapped[UUID] = mapped_column(ForeignKey("flats.id"), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
