from datetime import datetime
from uuid import UUID

from sqlalchemy import TIMESTAMP, ForeignKey, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base_class import Base


class Tower(Base):
    __tablename__ = "towers"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    complex_id: Mapped[UUID] = mapped_column(
        ForeignKey("apartment_complexes.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # short uppercase code (e.g. "OAK", "SUN2"), auto-derived from `name` at creation (superuser
    # can override before save); used by Module 3's receipt numbering — this is the only reason
    # this column exists.
    code: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    total_floors: Mapped[int] = mapped_column(Integer, nullable=False)
    total_flats: Mapped[int] = mapped_column(Integer, nullable=False)
    association_name: Mapped[str] = mapped_column(String(200), nullable=False)
    deactivated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )
