"""Per-tower sequential receipt numbering (backend.md §1.7). Incrementing `next_number` happens
with `SELECT ... FOR UPDATE` in the same transaction as the `receipts` insert (see
`app.services.receipts.next_receipt_number`) to guarantee no gaps/collisions under concurrent
mark-paid calls for the same tower."""

from uuid import UUID

from sqlalchemy import ForeignKey, Integer, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class ReceiptCounter(Base):
    __tablename__ = "receipt_counters"

    tower_id: Mapped[UUID] = mapped_column(ForeignKey("towers.id"), primary_key=True)
    next_number: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
