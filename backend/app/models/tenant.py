from datetime import date, datetime
from uuid import UUID

from sqlalchemy import TIMESTAMP, Boolean, Date, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base_class import Base


class Tenant(Base):
    """A tenant occupying a flat. Doubles as its own history table — a past tenancy is a row
    with `is_active=False` + `vacated_at` set; there is no separate `tenant_history` table
    (see `specs/02-flat-owner-tenant/overview.md` "Open questions"). `deactivated_at` is
    reserved for correcting a genuine data-entry mistake, never for a real vacate — that
    distinction must stay queryable (regression list in `backend.md`).
    """

    __tablename__ = "tenants"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    flat_id: Mapped[UUID] = mapped_column(ForeignKey("flats.id"), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    id_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    lease_start: Mapped[date] = mapped_column(Date, nullable=False)
    lease_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    vacated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    vacated_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deactivated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    __table_args__ = (
        Index(
            "uq_tenant_flat_active",
            "flat_id",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )
