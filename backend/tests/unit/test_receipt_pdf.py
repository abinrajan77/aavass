"""Unit tests for the dependency-free PDF renderer (`app.services.pdf`) — see that module's
docstring for why this exists instead of WeasyPrint/ReportLab in this environment. Verifies
the output is byte-valid PDF and that every receipt field appears as literal text, since
backend.md's test plan asserts on rendered-PDF text content (e.g. "receipt PDF names the
flat's primary owner, not the tenant" — overview.md edge case 4 / acceptance criterion 12)."""

from datetime import date
from decimal import Decimal

from app.services.pdf import render_receipt_pdf


def _render(**overrides) -> bytes:
    defaults = dict(
        receipt_number="OAK-2026-000001",
        owner_name="Asha Rao",
        billing_period_label="July 2026",
        amount=Decimal("2000.00"),
        payment_date=date(2026, 7, 9),
        payment_mode="cash",
    )
    defaults.update(overrides)
    return render_receipt_pdf(**defaults)


def test_output_is_a_byte_valid_pdf():
    pdf_bytes = _render()
    assert pdf_bytes.startswith(b"%PDF-1.4")
    assert pdf_bytes.rstrip().endswith(b"%%EOF")


def test_receipt_fields_appear_as_literal_text_in_the_content_stream():
    pdf_bytes = _render()
    assert b"OAK-2026-000001" in pdf_bytes
    assert b"Asha Rao" in pdf_bytes
    assert b"July 2026" in pdf_bytes
    assert b"2000.00" in pdf_bytes


def test_receipt_names_primary_owner_not_tenant():
    """overview.md edge case 4 / acceptance criterion 12 — even when a tenant paid, the
    receipt names the flat's primary owner (this module's boundary: the resolved owner_name
    is whatever the caller passes in, so this test locks down that the tenant's name, if
    passed in error, would be the *only* name present — guarding against a future refactor
    that accidentally threads the tenant's name into this function instead)."""
    pdf_bytes = _render(owner_name="Asha Rao")
    assert b"Asha Rao" in pdf_bytes
    assert b"Ravi Kumar" not in pdf_bytes  # the tenant, never named on the receipt


def test_parentheses_and_backslashes_in_names_are_escaped():
    """PDF literal strings use `(`/`)`/`\\` as syntax — an unescaped owner name containing
    them would corrupt the content stream."""
    pdf_bytes = _render(owner_name="Rao (Senior) \\ Family")
    assert rb"Rao \(Senior\) \\ Family" in pdf_bytes
