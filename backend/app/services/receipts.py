"""Receipt numbering (`receipt_counters`, row-locked) + PDF render/S3-upload — shared between
Module 3's maintenance dues and Module 4's special-collection dues
(`00-architecture-and-standards.md` §7)."""

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.receipt_counter import ReceiptCounter
from app.models.tower import Tower
from app.services import storage
from app.services.pdf import render_receipt_pdf


async def next_receipt_number(db: AsyncSession, tower_id: UUID) -> str:
    """Atomic upsert-and-increment on the tower's counter row via `INSERT ... ON CONFLICT DO
    UPDATE`, in the same transaction as the `receipts` insert (backend.md §1.7) — guarantees no
    gaps/collisions under concurrent mark-paid calls for the same tower, including the very
    first receipt (when no counter row exists yet): a plain "SELECT, then INSERT-if-missing" is
    racy there because two concurrent transactions can both see no row and both attempt the
    INSERT. `ON CONFLICT DO UPDATE` acquires the row lock as part of the single statement, so
    concurrent callers serialize on it instead of colliding.
    Format: `{tower_code}-{year}-{seq:06d}`, one sequence per tower shared across `due_type`
    (backend.md §1.6)."""
    stmt = (
        pg_insert(ReceiptCounter)
        .values(tower_id=tower_id, next_number=2)
        .on_conflict_do_update(
            index_elements=[ReceiptCounter.tower_id],
            set_={"next_number": ReceiptCounter.next_number + 1},
        )
        .returning(ReceiptCounter.next_number)
    )
    new_next_number = (await db.execute(stmt)).scalar_one()
    seq = new_next_number - 1

    tower = await db.get(Tower, tower_id)
    assert tower is not None, f"tower {tower_id} must exist (FK-enforced by receipt_counters)"
    year = date.today().year
    return f"{tower.code}-{year}-{seq:06d}"


async def render_and_upload_receipt(
    *,
    tower_id: UUID,
    label: str,
    receipt_number: str,
    owner_name: str,
    amount: Decimal,
    payment_date: date,
    payment_mode: str,
) -> str:
    """Renders the receipt PDF and uploads it to `receipts/{tower_id}/{receipt_id}.pdf`
    (`06-cloud-devops.md` §5), returning the S3 key to store on the `receipts` row."""
    receipt_id = uuid4()
    pdf_bytes = render_receipt_pdf(
        receipt_number=receipt_number,
        owner_name=owner_name,
        billing_period_label=label,
        amount=amount,
        payment_date=payment_date,
        payment_mode=payment_mode,
    )
    s3_key = f"receipts/{tower_id}/{receipt_id}.pdf"
    await storage.upload_bytes(key=s3_key, data=pdf_bytes, content_type="application/pdf")
    return s3_key
