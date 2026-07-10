from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class MarkPaidRequest(BaseModel):
    payment_date: date
    amount_received: Decimal = Field(gt=0, decimal_places=2)
    payment_mode: Literal["cash", "bank_transfer", "cheque"]
    reference_number: str | None = Field(default=None, max_length=100)
