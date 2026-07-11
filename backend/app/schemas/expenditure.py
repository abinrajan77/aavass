from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

PaymentMode = Literal["cash", "bank_transfer", "cheque"]


class ExpenditureCategory(str, Enum):
    cleaning = "cleaning"
    security = "security"
    repairs = "repairs"
    utilities = "utilities"
    other = "other"


class ExpenditureCreate(BaseModel):
    expenditure_date: date
    category: ExpenditureCategory
    description: str = Field(min_length=1)
    vendor_payee_name: str = Field(min_length=1, max_length=200)
    amount: Decimal = Field(gt=0, decimal_places=2)
    payment_mode: PaymentMode
    attachment_s3_key: str | None = None


class ComplexContributionCreate(BaseModel):
    expenditure_date: date
    description: str = Field(min_length=1)
    vendor_payee_name: str = Field(min_length=1, max_length=200)
    complex_total_amount: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    amount: Decimal = Field(
        gt=0,
        decimal_places=2,
        description="Tower's own share amount — the only figure posted to this tower's books.",
    )
    payment_mode: PaymentMode
    category: ExpenditureCategory = ExpenditureCategory.other
    attachment_s3_key: str | None = None


class ExpenditureUpdate(BaseModel):
    expenditure_date: date | None = None
    category: ExpenditureCategory | None = None
    description: str | None = Field(default=None, min_length=1)
    vendor_payee_name: str | None = Field(default=None, min_length=1, max_length=200)
    amount: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    payment_mode: PaymentMode | None = None
    attachment_s3_key: str | None = None


class ExpenditureOut(BaseModel):
    id: UUID
    tower_id: UUID
    expenditure_date: date
    category: ExpenditureCategory
    description: str
    vendor_payee_name: str
    amount: Decimal
    payment_mode: str
    attachment_s3_key: str | None
    is_complex_contribution: bool
    complex_total_amount: Decimal | None
    recorded_by: UUID
    created_at: datetime
    updated_at: datetime
    deactivated_at: datetime | None

    model_config = {"from_attributes": True}


class AttachmentUploadUrlRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: Literal["application/pdf", "image/jpeg", "image/png"]
    # Optional client-declared size, checked against the 10 MB ceiling before a presigned
    # URL is even issued (backend.md test plan item 11).
    content_length: int | None = Field(default=None, gt=0)


class AttachmentUploadUrlResponse(BaseModel):
    upload_url: str
    attachment_s3_key: str
    max_content_length: int


class AttachmentUrlResponse(BaseModel):
    url: str
