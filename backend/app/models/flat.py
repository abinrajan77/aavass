from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import TIMESTAMP, Enum, ForeignKey, Index, Integer, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base_class import Base


class Flat(Base):
    """A physical unit within a tower — the root entity Owner/FlatOwnership/Tenant hang off.

    `occupancy_status` is never written directly by a generic PUT — only the tenant
    create/vacate service functions (`app/services/occupancy.py`) may change it, so the
    "current resident" invariant documented in `specs/02-flat-owner-tenant/overview.md`
    always holds. See that spec's "Data model contract for downstream modules".
    """

    __tablename__ = "flats"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    tower_id: Mapped[UUID] = mapped_column(ForeignKey("towers.id"), nullable=False, index=True)
    flat_number: Mapped[str] = mapped_column(String(20), nullable=False)
    floor: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(
        Enum("1BHK", "2BHK", "3BHK", "OTHER", name="flat_type"), nullable=False
    )
    carpet_area_sqft: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    occupancy_status: Mapped[str] = mapped_column(
        Enum("owner_occupied", "tenant_occupied", "vacant", name="occupancy_status"),
        nullable=False,
        default="vacant",
        server_default="vacant",
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deactivated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    __table_args__ = (
        # One active flat_number per tower (a deactivated flat's number may be reused).
        Index(
            "uq_flat_tower_number_active",
            "tower_id",
            "flat_number",
            unique=True,
            postgresql_where=text("deactivated_at IS NULL"),
        ),
    )
