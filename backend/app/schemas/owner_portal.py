"""Owner self-service portal response schemas — backend.md §3.1-3.2."""

from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.schemas.report import CollectionReportRow, ExpenditureReportRow, TenantRegisterRow


class OwnedFlatSummary(BaseModel):
    flat_id: UUID
    tower_id: UUID
    tower_name: str
    flat_number: str
    occupancy_status: Literal["owner_occupied", "tenant_occupied", "vacant"]
    is_primary_owner: bool
    current_due_status: Literal["paid", "pending", "overdue", "no_active_due"]


class OwnedFlatsByTower(BaseModel):
    tower_id: UUID
    tower_name: str
    flats: list[OwnedFlatSummary]


class OwnedFlatsResponse(BaseModel):
    towers: list[OwnedFlatsByTower]


class ReceiptSummary(BaseModel):
    receipt_id: UUID
    receipt_number: str
    billing_period: str
    download_url: str


class OwnerFlatDashboardResponse(BaseModel):
    flat_id: UUID
    tower_id: UUID
    flat_number: str
    current_due: CollectionReportRow | None
    payment_history: list[CollectionReportRow]
    receipts: list[ReceiptSummary]
    tower_expenditures: list[ExpenditureReportRow]
    tenant_history: list[TenantRegisterRow]
    ytd_totals: dict[str, Decimal]
