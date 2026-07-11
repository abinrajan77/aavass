"""Report response schemas — backend.md §2.1-2.5, verbatim field shapes."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class CollectionReportRow(BaseModel):
    flat_number: str
    owner_names: list[str]
    resident_type: Literal["owner", "tenant"]
    resident_name: str
    amount_due: Decimal
    status: Literal["paid", "pending", "overdue"]
    payment_date: date | None = None
    payment_mode: Literal["cash", "bank_transfer", "cheque"] | None = None
    reference_number: str | None = None
    receipt_number: str | None = None


class CollectionReportResponse(BaseModel):
    tower_id: UUID
    billing_cycle_id: UUID
    billing_month: int
    billing_year: int
    generated_at: datetime
    items: list[CollectionReportRow]
    totals: dict[str, Decimal]


class OutstandingDueRow(BaseModel):
    flat_number: str
    due_type: Literal["maintenance", "special_collection"]
    owner_names: list[str]
    resident_name: str
    amount_due: Decimal
    due_date: date
    grace_period_days: int
    days_overdue: int


class OutstandingDuesReportResponse(BaseModel):
    tower_id: UUID
    as_of_date: date
    items: list[OutstandingDueRow]
    total_outstanding: Decimal


class ExpenditureReportRow(BaseModel):
    date: date
    category: Literal["cleaning", "security", "repairs", "utilities", "other"]
    description: str
    vendor_payee: str
    amount: Decimal
    payment_mode: str
    has_attachment: bool


class CategoryTotal(BaseModel):
    category: str
    total: Decimal


class ExpenditureReportResponse(BaseModel):
    tower_id: UUID
    period_start: date
    period_end: date
    items: list[ExpenditureReportRow]
    category_totals: list[CategoryTotal]
    grand_total: Decimal


class CollectionVsExpenditureResponse(BaseModel):
    tower_id: UUID
    period_label: str
    maintenance_collected: Decimal
    special_collection_collected: Decimal
    total_collected: Decimal
    total_expenditure: Decimal
    net: Decimal
    expenditure_by_category: list[CategoryTotal]


class TenantRegisterRow(BaseModel):
    flat_number: str
    tenant_name: str
    phone_number: str
    email: str | None = None
    lease_start: date
    lease_end: date | None = None
    is_current: bool


class TenantRegisterResponse(BaseModel):
    tower_id: UUID
    items: list[TenantRegisterRow]
