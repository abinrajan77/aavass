"""Notification-preview response schemas — backend.md §4. No delivery-status field and no send
action anywhere in this module (overview.md acceptance criterion 10) — deliberate omission, not
an oversight."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel

NotificationEvent = Literal["due_generated", "overdue_reminder", "payment_confirmed"]


class NotificationMessage(BaseModel):
    recipient: Literal["tenant", "owner"]
    recipient_name: str
    recipient_phone: str
    message_text: str


class NotificationPreviewResponse(BaseModel):
    event: NotificationEvent
    due_id: UUID
    flat_number: str
    messages: list[NotificationMessage]
