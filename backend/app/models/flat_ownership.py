from datetime import date, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import TIMESTAMP, Boolean, Date, ForeignKey, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.owner import Owner


class FlatOwnership(Base):
    """Links an `Owner` to a `Flat` for a span of time. Rows are never deleted or "soft
    deleted" — an ownership ends by setting `date_to`, which IS the audit history (PRD §6.2.2
    "System tracks ownership history").
    """

    __tablename__ = "flat_ownerships"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    flat_id: Mapped[UUID] = mapped_column(ForeignKey("flats.id"), nullable=False, index=True)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("owners.id"), nullable=False, index=True)
    is_primary_contact: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    date_from: Mapped[date] = mapped_column(Date, nullable=False)
    date_to: Mapped[date | None] = mapped_column(Date, nullable=True)  # NULL = currently active
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

    owner: Mapped["Owner"] = relationship()

    __table_args__ = (
        # Exactly one primary contact among currently-active ownerships, per flat.
        Index(
            "uq_flat_primary_contact_active",
            "flat_id",
            unique=True,
            postgresql_where=text("date_to IS NULL AND is_primary_contact"),
        ),
    )
