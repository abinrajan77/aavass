"""Draft notification message templates (backend.md §1, PRD §8.1 v1.0 manual notification
support). Global, not tower-scoped — tower/flat/due-specific values are substituted at request
time (`app.services.notifications`) against Module 2/3/4 data, never stored per-tower here.
Seeded once per `(event_type, recipient_role)` combination in this module's migration; v1.0 has
no admin-editable template screen, but the table shape supports one without a schema change."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import TIMESTAMP, Boolean, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base_class import Base


class NotificationTemplate(Base):
    __tablename__ = "notification_templates"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    # 'due_generated' | 'overdue_reminder' | 'payment_confirmed'
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # 'resident' | 'owner_copy'
    recipient_role: Mapped[str] = mapped_column(String(20), nullable=False)
    # 'generic' in v1.0; 'sms'/'whatsapp' reserved for v1.1 per-channel variants.
    channel: Mapped[str] = mapped_column(String(20), nullable=False, server_default="generic")
    template_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "event_type", "recipient_role", "channel", name="uq_notification_template_key"
        ),
    )
