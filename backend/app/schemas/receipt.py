from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.maintenance_due import MaintenanceDueOut


class ReceiptOut(BaseModel):
    id: UUID
    receipt_number: str
    owner_name_snapshot: str
    billing_period_label: str
    generated_at: datetime
    download_url: str


class MarkPaidResponse(BaseModel):
    due: MaintenanceDueOut
    receipt: ReceiptOut


class ReceiptDownloadOut(BaseModel):
    receipt_number: str
    download_url: str
