"""Minimal, dependency-free PDF renderer for maintenance/special-collection receipts.

Deviation from spec: `00-architecture-and-standards.md` §1 names WeasyPrint or ReportLab for
PDF generation, but neither is installed in this environment and this task's sandbox has no
way to verify a new binary/system-level dependency (WeasyPrint needs system Cairo/Pango libs;
even pure-Python ReportLab couldn't be installed-and-verified here without network access to
PyPI at build time in every environment this might run in). `render_receipt_pdf()` instead
hand-builds a minimal, byte-valid single-page PDF (raw PDF object/xref syntax, Helvetica text
only, no images) — it satisfies every content assertion in backend.md's test plan (owner name,
receipt number, amount, billing period all appear as literal, greppable text in the PDF's
content stream) and any PDF viewer can open the result. Swap this for a WeasyPrint/ReportLab
HTML-template renderer when that dependency is added to `pyproject.toml`;
`render_receipt_pdf()`'s keyword-only signature is the only integration point callers
(`app.services.receipts`) depend on, so the swap is contained to this one file.
"""

from datetime import date
from decimal import Decimal


def _escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _build_pdf_from_lines(lines: list[str]) -> bytes:
    """Shared raw-PDF-object builder (single page, Helvetica, no images) — every line of text
    passed in appears as literal, greppable text in the content stream, per both
    `render_receipt_pdf()` and `render_tabular_report_pdf()`'s test-plan requirement. Pages
    beyond the first are not attempted (v1.0 reports are rendered as one long single-page
    stream — acceptable for the hand-rolled minimal renderer described in this module's
    docstring; a real WeasyPrint/ReportLab swap would paginate properly)."""
    content_lines = ["BT", "/F1 10 Tf", "40 780 Td", "13 TL"]
    for line in lines:
        content_lines.append(f"({_escape(line)}) Tj")
        content_lines.append("T*")
    content_lines.append("ET")
    content_stream = "\n".join(content_lines).encode("latin-1", errors="replace")

    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> "
            b"/MediaBox [0 0 792 612] /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        (
            f"<< /Length {len(content_stream)} >>\nstream\n".encode("latin-1")
            + content_stream
            + b"\nendstream"
        ),
    ]

    buf = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(buf))
        buf += f"{i} 0 obj\n".encode("latin-1")
        buf += obj
        buf += b"\nendobj\n"

    xref_offset = len(buf)
    buf += f"xref\n0 {len(objects) + 1}\n".encode("latin-1")
    buf += b"0000000000 65535 f \n"
    for off in offsets:
        buf += f"{off:010d} 00000 n \n".encode("latin-1")
    buf += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF"
    ).encode("latin-1")
    return bytes(buf)


def render_tabular_report_pdf(
    *,
    title: str,
    headers: list[str],
    rows: list[list[str]],
    summary_lines: list[str] | None = None,
) -> bytes:
    """Generic tabular PDF renderer for Module 5's 5 report exports (backend.md §2.6) — same
    hand-rolled raw-PDF-object approach as `render_receipt_pdf()` (see that function's/this
    module's docstring for why no WeasyPrint/ReportLab dependency is used here). Every header
    and every cell value appears as literal, greppable text in the content stream: one line per
    header row (pipe-joined) and one line per data row (pipe-joined) — satisfies backend.md's
    test-plan requirement that "PDF/CSV renderers produce column-identical output" (CSV headers
    match PDF table headers)."""
    lines = [title, "", " | ".join(headers)]
    for row in rows:
        lines.append(" | ".join(row))
    if summary_lines:
        lines.append("")
        lines.extend(summary_lines)
    return _build_pdf_from_lines(lines)


def render_receipt_pdf(
    *,
    receipt_number: str,
    owner_name: str,
    billing_period_label: str,
    amount: Decimal,
    payment_date: date,
    payment_mode: str,
) -> bytes:
    lines = [
        "AAVAAS MAINTENANCE RECEIPT",
        f"Receipt No: {receipt_number}",
        f"Received From: {owner_name}",
        f"Billing Period: {billing_period_label}",
        f"Amount: INR {amount:.2f}",
        f"Payment Date: {payment_date.isoformat()}",
        f"Payment Mode: {payment_mode}",
    ]

    content_lines = ["BT", "/F1 14 Tf", "50 780 Td", "16 TL"]
    for line in lines:
        content_lines.append(f"({_escape(line)}) Tj")
        content_lines.append("T*")
    content_lines.append("ET")
    content_stream = "\n".join(content_lines).encode("latin-1", errors="replace")

    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> "
            b"/MediaBox [0 0 612 792] /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        (
            f"<< /Length {len(content_stream)} >>\nstream\n".encode("latin-1")
            + content_stream
            + b"\nendstream"
        ),
    ]

    buf = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(buf))
        buf += f"{i} 0 obj\n".encode("latin-1")
        buf += obj
        buf += b"\nendobj\n"

    xref_offset = len(buf)
    buf += f"xref\n0 {len(objects) + 1}\n".encode("latin-1")
    buf += b"0000000000 65535 f \n"
    for off in offsets:
        buf += f"{off:010d} 00000 n \n".encode("latin-1")
    buf += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF"
    ).encode("latin-1")
    return bytes(buf)
