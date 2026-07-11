"""Backend test plan: "PDF/CSV renderers produce column-identical output for the same report
(CSV headers match PDF table headers) for all 5 report types." `ReportTable.headers` is the
single list both renderers consume (`app.services.export.render_export_file`), so this test
verifies that invariant holds for hand-built tables spanning every report type — no DB needed,
these are plain dataclasses."""

import csv
import io

import pytest

from app.services.export import ReportTable, render_export_file

REPORT_TABLES = [
    ReportTable(
        title="Monthly Collection Report",
        headers=["flat_number", "owner_names", "status", "amount_due"],
        rows=[
            ["101", "Asha Rao", "paid", "2000.00"],
            ["102", "Vikram Singh", "pending", "1800.00"],
        ],
        summary_lines=["total_due: 3800.00"],
    ),
    ReportTable(
        title="Outstanding Dues Report",
        headers=["flat_number", "due_type", "amount_due", "days_overdue"],
        rows=[["103", "maintenance", "2200.00", "4"]],
        summary_lines=["total_outstanding: 2200.00"],
    ),
    ReportTable(
        title="Expenditure Report",
        headers=["date", "category", "amount", "has_attachment"],
        rows=[["2026-07-05", "cleaning", "1500.00", "False"]],
        summary_lines=["grand_total: 1500.00"],
    ),
    ReportTable(
        title="Collection vs Expenditure Summary",
        headers=["category", "total"],
        rows=[["repairs", "3000.00"]],
        summary_lines=["net: 1800.00"],
    ),
    ReportTable(
        title="Tenant Register",
        headers=["flat_number", "tenant_name", "is_current"],
        rows=[["101", "Ravi Kumar", "True"]],
        summary_lines=[],
    ),
]


@pytest.mark.parametrize("table", REPORT_TABLES, ids=lambda t: t.title)
def test_csv_header_row_matches_pdf_headers(table: ReportTable):
    csv_bytes, csv_content_type = render_export_file(table, format="csv")
    assert csv_content_type == "text/csv"
    rows = list(csv.reader(io.StringIO(csv_bytes.decode("utf-8"))))
    assert rows[0] == table.headers

    pdf_bytes, pdf_content_type = render_export_file(table, format="pdf")
    assert pdf_content_type == "application/pdf"
    assert pdf_bytes.startswith(b"%PDF-1.4")
    pdf_text = pdf_bytes.decode("latin-1", errors="replace")
    for header in table.headers:
        assert header in pdf_text


@pytest.mark.parametrize("table", REPORT_TABLES, ids=lambda t: t.title)
def test_every_row_cell_appears_in_both_renderers(table: ReportTable):
    csv_bytes, _ = render_export_file(table, format="csv")
    csv_text = csv_bytes.decode("utf-8")
    pdf_bytes, _ = render_export_file(table, format="pdf")
    pdf_text = pdf_bytes.decode("latin-1", errors="replace")

    for row in table.rows:
        for cell in row:
            assert cell in csv_text
            assert cell in pdf_text
