from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AuditLogEntryOut(BaseModel):
    id: UUID
    tower_id: UUID | None
    user_id: UUID | None
    actor_label: str
    action: str
    entity_type: str
    entity_id: UUID
    before: dict | None
    after: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}
