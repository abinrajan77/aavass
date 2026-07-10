# STUB for Module 2 — owned by 02-flat-owner-tenant, minimal fields only for Module 3's
# FK/read needs.
"""See `app/models/flat.py`'s module docstring for the rationale. Only `is_primary_contact` and
`full_name` are modeled — no co-ownership percentage split, no contact details, no history."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import TIMESTAMP, Boolean, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base_class import Base


class Owner(Base):
    __tablename__ = "owners"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    flat_id: Mapped[UUID] = mapped_column(ForeignKey("flats.id"), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_primary_contact: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
