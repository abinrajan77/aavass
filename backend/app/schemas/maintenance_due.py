from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class MaintenanceDueOut(BaseModel):
    id: UUID
    billing_cycle_id: UUID
    flat_id: UUID
    flat_number: str
    amount: Decimal
    assigned_to_type: Literal["tenant", "owner"]
    assigned_to_name_snapshot: str
    due_date: date
    status: Literal["pending", "paid", "overdue"]
    created_at: datetime

    model_config = {"from_attributes": True}


class BillingDashboardStatsOut(BaseModel):
    total_collected_this_cycle: Decimal
    pending_count: int
    overdue_amount: Decimal
