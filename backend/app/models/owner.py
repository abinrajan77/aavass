from datetime import datetime
from uuid import UUID

from sqlalchemy import TIMESTAMP, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base_class import Base


class Owner(Base):
    """A person who owns one or more flats — deliberately NOT tower-scoped (PRD §6.2.2: "an
    owner may be linked to multiple flats across towers"). Tower isolation for reads/writes is
    enforced at the `FlatOwnership`/`Flat` level, never on this table directly.
    """

    __tablename__ = "owners"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    # nullable: an owner can exist before/without a login account (admin-entered); linked once
    # they register a Flat Owner account.
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id"), unique=True, nullable=True
    )
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    id_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deactivated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
