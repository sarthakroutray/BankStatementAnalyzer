import io
from datetime import date
from decimal import Decimal
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet

from app.services.pdf_extractor import (
    extract_cell_text,
    extract_tables_from_pdf,
    parse_opendataloader_json,
)


def test_extract_cell_text():
    cell_dict = {
        "content": "Hello",
        "kids": [
            {"content": "World", "kids": [{"content": "!"}]}
        ]
    }
    assert extract_cell_text(cell_dict) == "Hello World !"


def test_parse_opendataloader_json():
    mock_json = {
        "kids": [
            {
                "type": "table",
                "rows": [
                    {
                        "cells": [
                            {"content": "Date"},
                            {"content": "Description"},
                            {"content": "Debit"},
                            {"content": "Credit"},
                            {"content": "Balance"},
                        ]
                    },
                    {
                        "cells": [
                            {"content": "2024-02-01"},
                            {"content": "Target Store"},
                            {"content": "45.20"},
                            {"content": ""},
                            {"content": "800.00"},
                        ]
                    }
                ]
            }
        ]
    }
    tables = parse_opendataloader_json(mock_json)
    assert len(tables) == 1
    assert len(tables[0]) == 2
    assert tables[0][0] == ["Date", "Description", "Debit", "Credit", "Balance"]
    assert tables[0][1] == ["2024-02-01", "Target Store", "45.20", "", "800.00"]


def test_extract_tables_from_real_pdf():
    # Build in-memory PDF using ReportLab
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    elements.append(Paragraph("Account Activity", styles["Heading1"]))

    table_data = [
        ["Date", "Description", "Debit", "Credit", "Balance"],
        ["2024-01-10", "Starbucks Store #991", "5.75", "", "1200.00"],
        ["2024-01-12", "Whole Foods Market", "62.30", "", "1137.70"],
        ["2024-01-15", "Payroll Deposit", "", "2000.00", "3137.70"],
    ]
    t = Table(table_data)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(t)
    doc.build(elements)

    pdf_bytes = buf.getvalue()
    txns = extract_tables_from_pdf(pdf_bytes, filename="test_statement.pdf")

    assert len(txns) >= 3
    starbucks_txn = next((x for x in txns if "Starbucks" in x.description), None)
    assert starbucks_txn is not None
    assert starbucks_txn.amount == Decimal("5.75")
    assert starbucks_txn.txn_type == "DEBIT"
    assert starbucks_txn.category == "Food & Dining"
