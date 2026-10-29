import io
from datetime import date
from decimal import Decimal
import numpy as np
import pytest
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

from app.services.normalizer import (
    detect_column_headers,
    infer_columns_statistically,
    normalize_table_rows,
    parse_amount,
    parse_date,
)
from app.services.pdf_extractor import (
    extract_raw_records_from_image_array,
    extract_tables_from_pdf,
    extract_transactions_via_pypdf_fallback,
    is_amount,
    parse_amt,
)


def test_hdfc_bank_format_extraction():
    """HDFC: Date | Narration | Chq/Ref No | Value Dt | Withdrawal Amt. | Deposit Amt. | Closing Balance"""
    table = [
        ["Date", "Narration", "Chq/Ref No", "Value Dt", "Withdrawal Amt.", "Deposit Amt.", "Closing Balance"],
        ["01/01/2024", "UPI/401293847291/SWIGGY/BANGALORE", "401293847291", "01/01/2024", "450.00", "", "15550.00"],
        ["02/01/2024", "ACH-SALARY CREDIT-ACME CORP", "ACH0098231", "02/01/2024", "", "75000.00", "90550.00"],
        ["03/01/2024", "NETFLIX ENTERTAINMENT SUBSCRIPTION", "00000000", "03/01/2024", "649.00", "", "89901.00"],
    ]
    txns = normalize_table_rows(table, use_ml=True)
    assert len(txns) == 3

    assert txns[0].txn_date == date(2024, 1, 1)
    assert txns[0].amount == Decimal("450.00")
    assert txns[0].txn_type == "DEBIT"
    assert txns[0].category == "Food & Dining"
    assert txns[0].balance == Decimal("15550.00")

    assert txns[1].txn_date == date(2024, 1, 2)
    assert txns[1].amount == Decimal("75000.00")
    assert txns[1].txn_type == "CREDIT"
    assert txns[1].category == "Income & Salary"
    assert txns[1].balance == Decimal("90550.00")

    assert txns[2].txn_type == "DEBIT"
    assert txns[2].amount == Decimal("649.00")
    assert txns[2].category == "Entertainment & Subscriptions"


def test_icici_bank_format_extraction():
    """ICICI: Value Date | Transaction Date | Cheque Number | Transaction Remarks | Debit Amount (INR) | Credit Amount (INR) | Balance (INR)"""
    table = [
        ["Value Date", "Transaction Date", "Cheque Number", "Transaction Remarks", "Debit Amount (INR)", "Credit Amount (INR)", "Balance (INR)"],
        ["05/01/2024", "05/01/2024", "000123", "ZERODHA BROKING LTD INVEST", "5000.00", "", "45000.00"],
        ["06/01/2024", "06/01/2024", "-", "DIVIDEND CREDIT TATA MOTORS", "", "1200.00", "46200.00"],
        ["07/01/2024", "07/01/2024", "-", "APOLLO PHARMACY HEALTHCARE", "850.50", "", "45349.50"],
    ]
    txns = normalize_table_rows(table, use_ml=True)
    assert len(txns) == 3

    assert txns[0].txn_date == date(2024, 1, 5)
    assert txns[0].amount == Decimal("5000.00")
    assert txns[0].txn_type == "DEBIT"
    assert txns[0].category == "Investments"

    assert txns[1].txn_type == "CREDIT"
    assert txns[1].amount == Decimal("1200.00")
    assert txns[1].category == "Income & Salary"

    assert txns[2].txn_type == "DEBIT"
    assert txns[2].amount == Decimal("850.50")
    assert txns[2].category == "Healthcare"


def test_sbi_bank_format_with_named_months():
    """SBI: Txn Date | Value Date | Description | Ref No./Cheque No. | Debit | Credit | Balance with '01 Jan 2024'"""
    table = [
        ["Txn Date", "Value Date", "Description", "Ref No./Cheque No.", "Debit", "Credit", "Balance"],
        ["1 Jan 2024", "1 Jan 2024", "ELECTRICITY BILL TATA POWER", "REF12345", "1450.00", "", "23550.00"],
        ["2 Jan 2024", "2 Jan 2024", "RELIANCE SMART GROCERY SUPERMARKET", "REF67890", "3200.00", "", "20350.00"],
        ["3 Jan 2024", "3 Jan 2024", "INTEREST CREDIT SB ACCOUNT", "REF00000", "", "350.00", "20700.00"],
    ]
    txns = normalize_table_rows(table, use_ml=True)
    assert len(txns) == 3

    assert txns[0].txn_date == date(2024, 1, 1)
    assert txns[0].amount == Decimal("1450.00")
    assert txns[0].category == "Utilities & Bills"

    assert txns[1].txn_date == date(2024, 1, 2)
    assert txns[1].amount == Decimal("3200.00")
    assert txns[1].category == "Groceries"

    assert txns[2].txn_type == "CREDIT"
    assert txns[2].amount == Decimal("350.00")


def test_kotak_bank_format_amount_with_type_column():
    """Kotak: Date | Transaction Details | Amount | Dr / Cr | Balance"""
    table = [
        ["Date", "Transaction Details", "Amount", "Dr / Cr", "Balance"],
        ["10/01/2024", "UBER TRIP MUMBAI", "320.00", "DR", "15000.00"],
        ["11/01/2024", "REFUND MYNTRA DESIGNS", "1499.00", "CR", "16499.00"],
        ["12/01/2024", "FLIPKART INTERNET RETAIL", "2999.00", "DR", "13500.00"],
    ]
    txns = normalize_table_rows(table, use_ml=True)
    assert len(txns) == 3

    assert txns[0].txn_type == "DEBIT"
    assert txns[0].amount == Decimal("320.00")
    assert txns[0].category == "Travel & Transport"

    assert txns[1].txn_type == "CREDIT"
    assert txns[1].amount == Decimal("1499.00")

    assert txns[2].txn_type == "DEBIT"
    assert txns[2].amount == Decimal("2999.00")
    assert txns[2].category == "Shopping"


def test_chase_and_boa_signed_amounts_and_currency():
    """Bank of America: Date | Description | Amount | Running Bal with signed and parenthesized amounts"""
    table = [
        ["Date", "Description", "Amount", "Running Bal."],
        ["01/10/2024", "Whole Foods Market", "-$84.50", "$3,415.50"],
        ["01/11/2024", "Corporate Direct Deposit", "+$3,000.00", "$6,415.50"],
        ["01/12/2024", "Starbucks Store #102", "($5.75)", "$6,409.75"],
    ]
    txns = normalize_table_rows(table, use_ml=True)
    assert len(txns) == 3

    assert txns[0].txn_date == date(2024, 1, 10)
    assert txns[0].amount == Decimal("84.50")
    assert txns[0].txn_type == "DEBIT"
    assert txns[0].category in ("Groceries", "Food & Dining")

    assert txns[1].txn_date == date(2024, 1, 11)
    assert txns[1].amount == Decimal("3000.00")
    assert txns[1].txn_type == "CREDIT"
    assert txns[1].category == "Income & Salary"

    assert txns[2].txn_date == date(2024, 1, 12)
    assert txns[2].amount == Decimal("5.75")
    assert txns[2].txn_type == "DEBIT"
    assert txns[2].category == "Food & Dining"


def test_chase_multi_section_format():
    """Chase: Statement organized by section headers 'Deposits and Additions' vs 'Withdrawals and Subtractions'"""
    table = [
        ["Date", "Description", "Amount"],
        ["Deposits and Additions", "", ""],
        ["01/05/2024", "Payroll Direct Deposit", "2500.00"],
        ["01/06/2024", "Zelle Payment from Alice", "150.00"],
        ["ATM & Debit Card Subtractions", "", ""],
        ["01/07/2024", "Chipotle Mexican Grill", "14.25"],
        ["01/08/2024", "Target Store #221", "48.90"],
    ]
    txns = normalize_table_rows(table, use_ml=True)
    assert len(txns) == 4

    assert txns[0].txn_type == "CREDIT"
    assert txns[0].amount == Decimal("2500.00")
    assert txns[0].category == "Income & Salary"

    assert txns[1].txn_type == "CREDIT"
    assert txns[1].amount == Decimal("150.00")

    assert txns[2].txn_type == "DEBIT"
    assert txns[2].amount == Decimal("14.25")
    assert txns[2].category == "Food & Dining"

    assert txns[3].txn_type == "DEBIT"
    assert txns[3].amount == Decimal("48.90")
    assert txns[3].category == "Groceries"


def test_multiline_narration_merging():
    """Verify that secondary narration lines without date/amounts merge into previous transaction."""
    table = [
        ["Date", "Narration", "Withdrawal", "Deposit", "Balance"],
        ["01/01/2024", "UPI/401293847291/Payment to Swiggy", "350.00", "", "10000.00"],
        ["", "Bangalore IN / Order #991023", "", "", ""],
        ["02/01/2024", "NEFT-SALARY-ACME TECH CORP", "", "50000.00", "60000.00"],
        ["", "Payroll Batch ID 44021 Jan 2024", "", "", ""],
    ]
    txns = normalize_table_rows(table, use_ml=True)
    assert len(txns) == 2

    assert "Swiggy" in txns[0].description
    assert "Bangalore IN / Order #991023" in txns[0].description
    assert txns[0].category == "Food & Dining"

    assert "ACME TECH CORP" in txns[1].description
    assert "Payroll Batch ID 44021" in txns[1].description
    assert txns[1].category == "Income & Salary"


def test_multi_row_headers():
    """Verify table with headers split across 2 consecutive rows."""
    table = [
        ["Transaction", "Transaction", "Cheque", "Amount", "Amount", "Balance"],
        ["Date", "Particulars", "Number", "Debit", "Credit", ""],
        ["2024-02-01", "McDonalds Burger Order", "001", "12.50", "", "1500.00"],
        ["2024-02-02", "Tax Refund IRS Direct Dep", "002", "", "450.00", "1950.00"],
    ]
    txns = normalize_table_rows(table, use_ml=True)
    assert len(txns) == 2
    assert txns[0].amount == Decimal("12.50")
    assert txns[0].txn_type == "DEBIT"
    assert txns[0].category == "Food & Dining"
    assert txns[1].amount == Decimal("450.00")
    assert txns[1].txn_type == "CREDIT"
    assert txns[1].category == "Income & Salary"


def test_table_without_headers_statistical_inference():
    """Verify tables with zero header rows via statistical column inference."""
    raw_data = [
        ["2024-03-01", "Starbucks Store #991", "4.50", "", "1200.00"],
        ["2024-03-02", "Whole Foods Market", "65.20", "", "1134.80"],
        ["2024-03-03", "Shell Oil Gas Station", "40.00", "", "1094.80"],
        ["2024-03-04", "Monthly Salary Deposit", "", "3500.00", "4594.80"],
    ]
    txns = normalize_table_rows(raw_data, use_ml=True)
    assert len(txns) == 4
    assert txns[0].txn_date == date(2024, 3, 1)
    assert txns[0].amount == Decimal("4.50")
    assert txns[0].txn_type == "DEBIT"
    assert txns[3].txn_type == "CREDIT"
    assert txns[3].amount == Decimal("3500.00")


def test_rupee_currency_and_european_decimals():
    """Verify ₹ symbol, Rs., and European decimal notation in parse_amount."""
    assert is_amount("₹15,000.00")
    assert is_amount("Rs. 450.50")
    assert is_amount("INR 120.00")
    assert is_amount("€1.250,50")

    amt1, hint1 = parse_amount("₹15,000.00")
    assert amt1 == Decimal("15000.00")

    amt2, hint2 = parse_amount("Rs. 450.50 DR")
    assert amt2 == Decimal("450.50")
    assert hint2 == "DEBIT"

    amt3, hint3 = parse_amount("€1.250,50")
    assert amt3 == Decimal("1250.50")

    amt4, hint4 = parse_amount("125,50 CR")
    assert amt4 == Decimal("125.50")
    assert hint4 == "CREDIT"


def test_ocr_extraction_with_named_month_and_3_amounts():
    """Verify RapidOCR simulation with named months (15-Jan-2024) and 3 amount columns (Debit, Credit, Balance)."""
    test_boxes = [
        # Header line
        ([[10, 10], [50, 10], [50, 25], [10, 25]], "Date", 0.99),
        ([[60, 10], [200, 10], [200, 25], [60, 25]], "Particulars", 0.99),
        ([[210, 10], [270, 10], [270, 25], [210, 25]], "Debit", 0.99),
        ([[280, 10], [340, 10], [340, 25], [280, 25]], "Credit", 0.99),
        ([[350, 10], [420, 10], [420, 25], [350, 25]], "Balance", 0.99),
        # Row 1: Debit row with 0.00 credit
        ([[10, 35], [50, 35], [50, 50], [10, 50]], "15-Jan-2024", 0.99),
        ([[60, 35], [200, 35], [200, 50], [60, 50]], "Uber Ride", 0.99),
        ([[210, 35], [270, 35], [270, 50], [210, 50]], "250.00", 0.99),
        ([[280, 35], [340, 35], [340, 50], [280, 50]], "0.00", 0.99),
        ([[350, 35], [420, 35], [420, 50], [350, 50]], "4750.00", 0.99),
        # Continuation line for Row 1
        ([[60, 55], [200, 55], [200, 70], [60, 70]], "Delhi to Airport", 0.99),
        # Row 2: Credit row with 0.00 debit
        ([[10, 75], [50, 75], [50, 90], [10, 90]], "16-Jan-2024", 0.99),
        ([[60, 75], [200, 75], [200, 90], [60, 90]], "Stipend Transfer", 0.99),
        ([[210, 75], [270, 75], [270, 90], [210, 90]], "0.00", 0.99),
        ([[280, 75], [340, 75], [340, 90], [280, 90]], "10000.00", 0.99),
        ([[350, 75], [420, 75], [420, 90], [350, 90]], "14750.00", 0.99),
    ]

    class MockOCR:
        def __call__(self, img):
            return test_boxes, 0.0

    import app.services.pdf_extractor as pe
    orig_ocr = pe.get_ocr_engine
    pe.get_ocr_engine = lambda: MockOCR()
    try:
        dummy_img = np.zeros((120, 500, 3), dtype=np.uint8)
        records, final_bal = extract_raw_records_from_image_array(dummy_img, running_balance=Decimal("5000.00"))
        assert len(records) == 2

        assert records[0]["txn_date"] == date(2024, 1, 15)
        assert records[0]["amount"] == Decimal("250.00")
        assert records[0]["txn_type"] == "DEBIT"
        assert "Delhi to Airport" in records[0]["description"]

        assert records[1]["txn_date"] == date(2024, 1, 16)
        assert records[1]["amount"] == Decimal("10000.00")
        assert records[1]["txn_type"] == "CREDIT"
        assert final_bal == Decimal("14750.00")
    finally:
        pe.get_ocr_engine = orig_ocr


def test_pypdf_fallback_multipage_text_pdf(tmp_path):
    """Generate a multi-page text PDF with various date formats and multiline text, and test pypdf fallback."""
    pdf_file = tmp_path / "diverse_statement.pdf"
    doc = SimpleDocTemplate(str(pdf_file), pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()

    elements.append(Paragraph("Bank Statement", styles["Heading1"]))
    table_data = [
        ["Date", "Narration", "Debit", "Credit", "Balance"],
        ["01/01/2024", "Starbucks Store #991", "5.50", "", "1500.00"],
        ["", "Seattle WA Store Order", "", "", ""],
        ["15 Jan 2024", "Salary NEFT Direct Deposit", "", "4500.00", "6000.00"],
        ["2024-01-20", "Uber Trip to Airport", "42.00", "", "5958.00"],
    ]
    t = Table(table_data)
    elements.append(t)
    doc.build(elements)

    txns = extract_transactions_via_pypdf_fallback(str(pdf_file))
    assert len(txns) >= 3
    dates = [t.txn_date for t in txns]
    assert date(2024, 1, 1) in dates
    assert date(2024, 1, 15) in dates
    assert date(2024, 1, 20) in dates


def test_pure_time_strings_rejected_by_parse_date():
    """Verify that pure timestamps (e.g. '04:26 pm', '10:00 am', '16:26:00') are never parsed as dates."""
    for time_str in ["04:26 pm", "10:00 am", "16:26:00", "12:30", "09:15:30 PM"]:
        assert parse_date(time_str) is None, f"{time_str} should be rejected as pure time"


def test_vertical_stream_fallback_phonepe_style(tmp_path):
    """Verify pypdf fallback extraction on statements where Date, Time, Type, Amount, and Narration are vertical text lines."""
    pdf_file = tmp_path / "phonepe_style.pdf"
    doc = SimpleDocTemplate(str(pdf_file), pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()

    elements.append(Paragraph("Transaction Statement for 9897996621", styles["Heading1"]))
    elements.append(Paragraph("19 Feb, 2026 - 21 Mar, 2026", styles["Normal"]))

    table_data = [
        ["Date"], ["Transaction Details"], ["Type"], ["Amount"],
        ["Mar 21, 2026"], ["04:26 pm"], ["DEBIT"], ["Rs. 90.00"], ["Paid to Mukesh Kumawat"], ["Transaction ID T260321162612"],
        ["Mar 20, 2026"], ["02:09 pm"], ["CREDIT"], ["Rs. 5000.00"], ["Received from Rohit Saluja"], ["Transaction ID T260320140937"],
        ["Mar 19, 2026"], ["10:30 pm"], ["CREDIT"], ["Rs. 35.00"], ["Received from Udit Gaba"], ["Transaction ID T260319223059"],
    ]
    t = Table(table_data)
    elements.append(t)
    doc.build(elements)

    txns = extract_transactions_via_pypdf_fallback(str(pdf_file))
    assert len(txns) == 3

    assert txns[0].txn_date == date(2026, 3, 21)
    assert txns[0].amount == Decimal("90.00")
    assert txns[0].txn_type == "DEBIT"
    assert "Mukesh Kumawat" in txns[0].description

    assert txns[1].txn_date == date(2026, 3, 20)
    assert txns[1].amount == Decimal("5000.00")
    assert txns[1].txn_type == "CREDIT"
    assert "Rohit Saluja" in txns[1].description

    assert txns[2].txn_date == date(2026, 3, 19)
    assert txns[2].amount == Decimal("35.00")
    assert txns[2].txn_type == "CREDIT"


def test_headerless_cheque_number_isolation():
    """Verify that statistical inference correctly isolates Cheque/Ref numbers from Debit/Credit/Balance columns."""
    rows = [
        ["2024-01-01", "Swiggy Food Order", "000101", "2024-01-01", "450.00", "", "15550.00"],
        ["2024-01-02", "Salary Direct Credit", "000102", "2024-01-02", "", "75000.00", "90550.00"],
        ["2024-01-03", "Netflix Entertainment", "000103", "2024-01-03", "649.00", "", "89901.00"],
    ]
    mapping = infer_columns_statistically(rows)
    assert mapping.date_idx == 0
    assert mapping.desc_idx == 1
    assert mapping.ref_idx == 2
    assert mapping.debit_idx == 4
    assert mapping.credit_idx == 5
    assert mapping.balance_idx == 6

    txns = normalize_table_rows(rows, use_ml=True)
    assert len(txns) == 3
    assert txns[0].amount == Decimal("450.00")
    assert txns[0].txn_type == "DEBIT"
    assert txns[1].amount == Decimal("75000.00")
    assert txns[1].txn_type == "CREDIT"
    assert txns[2].amount == Decimal("649.00")
    assert txns[2].txn_type == "DEBIT"


def test_multipage_continuation_table_state_inheritance():
    """Verify that Page 2 continuation tables inherit column mapping and balance delta from Page 1."""
    page1_table = [
        ["Date", "Description", "Amount", "Balance"],
        ["01/01/2024", "Initial Deposit", "5000.00", "5000.00"],
        ["02/01/2024", "Grocery Shopping", "200.00", "4800.00"],
    ]
    page2_table = [
        # Page 2 has no headers, just continues transactions
        ["03/01/2024", "Utility Electricity Bill", "150.00", "4650.00"],
        ["04/01/2024", "Freelance Payment", "1000.00", "5650.00"],
    ]

    txns1, map1, bal1 = normalize_table_rows(page1_table, use_ml=True, return_state=True)
    assert len(txns1) == 2
    assert bal1 == Decimal("4800.00")

    txns2, map2, bal2 = normalize_table_rows(
        page2_table,
        use_ml=True,
        inherited_mapping=map1,
        initial_balance=bal1,
        return_state=True,
    )
    assert len(txns2) == 2
    assert txns2[0].amount == Decimal("150.00")
    assert txns2[0].txn_type == "DEBIT"
    assert txns2[0].balance == Decimal("4650.00")

    # Freelance Payment balance increased from 4650 to 5650 -> delta +1000 -> CREDIT
    assert txns2[1].amount == Decimal("1000.00")
    assert txns2[1].txn_type == "CREDIT"
    assert txns2[1].balance == Decimal("5650.00")
    assert bal2 == Decimal("5650.00")


def test_ocr_extraction_yearless_dates_and_opening_balance():
    """Verify OCR handles yearless dates (01/12) and opening balance rows with no description."""
    test_boxes = [
        # Document header with statement date
        ([[10, 5], [200, 5], [200, 20], [10, 20]], "Jan 7, 2022 Page 2 of 5", 0.99),
        # Table Header
        ([[10, 30], [50, 30], [50, 45], [10, 45]], "Dates", 0.99),
        ([[60, 30], [150, 30], [150, 45], [60, 45]], "Description", 0.99),
        ([[160, 30], [220, 30], [220, 45], [160, 45]], "Charges", 0.99),
        ([[230, 30], [300, 30], [300, 45], [230, 45]], "Balance", 0.99),
        # Opening balance row: date and balance only, no description
        ([[10, 50], [50, 50], [50, 65], [10, 65]], "01/12", 0.99),
        ([[230, 50], [300, 50], [300, 65], [230, 65]], "10000.00", 0.99),
        # Row 1: Debit
        ([[10, 70], [50, 70], [50, 85], [10, 85]], "02/12", 0.99),
        ([[60, 70], [150, 70], [150, 85], [60, 85]], "Coffee Shop", 0.99),
        ([[160, 70], [220, 70], [220, 85], [160, 85]], "50.00", 0.99),
        ([[230, 70], [300, 70], [300, 85], [230, 85]], "9950.00", 0.99),
    ]

    class MockOCR:
        def __call__(self, img):
            return test_boxes, 0.0

    import app.services.pdf_extractor as pe
    orig_ocr = pe.get_ocr_engine
    pe.get_ocr_engine = lambda: MockOCR()
    try:
        dummy_img = np.zeros((100, 400, 3), dtype=np.uint8)
        records, final_bal = extract_raw_records_from_image_array(dummy_img)
        assert len(records) == 1
        # Year rolled back from 2022 to 2021 because statement month is Jan (1) and txn month is Dec (12)
        assert records[0]["txn_date"] == date(2021, 12, 2)
        assert records[0]["amount"] == Decimal("50.00")
        assert records[0]["txn_type"] == "DEBIT"
        assert records[0]["balance"] == Decimal("9950.00")
        assert final_bal == Decimal("9950.00")
    finally:
        pe.get_ocr_engine = orig_ocr


def test_german_bank_format_extraction():
    """Deutsche Bank: Buchungstag | Vorgang / Verwendungszweck | Soll | Haben | Saldo with European decimal dots and commas."""
    table = [
        ["Buchungstag", "Vorgang / Verwendungszweck", "Soll", "Haben", "Saldo"],
        ["15.01.2024", "REWE Supermarkt Einkauf", "45,50", "", "2.454,50"],
        ["16.01.2024", "Gehalt ACME Tech GmbH", "", "3.000,00", "5.454,50"],
        ["17.01.2024", "Deutsche Bahn Fahrkarte", "89,00", "", "5.365,50"],
    ]
    txns = normalize_table_rows(table, use_ml=True)
    assert len(txns) == 3
    assert txns[0].txn_date == date(2024, 1, 15)
    assert txns[0].amount == Decimal("45.50")
    assert txns[0].txn_type == "DEBIT"
    assert txns[0].balance == Decimal("2454.50")

    assert txns[1].txn_date == date(2024, 1, 16)
    assert txns[1].amount == Decimal("3000.00")
    assert txns[1].txn_type == "CREDIT"
    assert txns[1].balance == Decimal("5454.50")

    assert txns[2].txn_date == date(2024, 1, 17)
    assert txns[2].amount == Decimal("89.00")
    assert txns[2].txn_type == "DEBIT"
    assert txns[2].balance == Decimal("5365.50")


def test_french_bank_format_extraction():
    """BNP Paribas: Date d'opération | Libellé de l'opération | Débit | Crédit | Solde with French accents and space thousands."""
    table = [
        ["Date d'opération", "Libellé de l'opération", "Débit", "Crédit", "Solde"],
        ["10/02/2024", "CARREFOUR HYPERMARCHE", "62,40", "", "1 850,00"],
        ["11/02/2024", "VIREMENT SALAIRE DIRECT", "", "2 500,00", "4 350,00"],
    ]
    txns = normalize_table_rows(table, use_ml=True)
    assert len(txns) == 2
    assert txns[0].txn_date == date(2024, 2, 10)
    assert txns[0].amount == Decimal("62.40")
    assert txns[0].txn_type == "DEBIT"
    assert txns[0].balance == Decimal("1850.00")

    assert txns[1].txn_date == date(2024, 2, 11)
    assert txns[1].amount == Decimal("2500.00")
    assert txns[1].txn_type == "CREDIT"
    assert txns[1].balance == Decimal("4350.00")


def test_uk_bank_money_out_in_format():
    """Barclays / Monzo: Date | Description | Money Out (£) | Money In (£) | Balance (£)"""
    table = [
        ["Date", "Description", "Money Out (£)", "Money In (£)", "Balance (£)"],
        ["05/03/2024", "TFL Travel Underground London", "£3.40", "", "£1,250.00"],
        ["06/03/2024", "Client Consulting Fee Payout", "", "£750.00", "£2,000.00"],
    ]
    txns = normalize_table_rows(table, use_ml=True)
    assert len(txns) == 2
    assert txns[0].txn_date == date(2024, 3, 5)
    assert txns[0].amount == Decimal("3.40")
    assert txns[0].txn_type == "DEBIT"
    assert txns[0].category == "Travel & Transport"

    assert txns[1].txn_date == date(2024, 3, 6)
    assert txns[1].amount == Decimal("750.00")
    assert txns[1].txn_type == "CREDIT"
    assert txns[1].balance == Decimal("2000.00")


def test_spanish_bank_format_extraction():
    """Santander / BBVA: Fecha | Concepto | Cargo | Abono | Saldo"""
    table = [
        ["Fecha", "Concepto", "Cargo", "Abono", "Saldo"],
        ["20/01/2024", "MERCADONA SUPERMERCADO", "38,25", "", "3.120,50"],
        ["22/01/2024", "TRANSFERENCIA NOMINA MENSUAL", "", "1.800,00", "4.920,50"],
    ]
    txns = normalize_table_rows(table, use_ml=True)
    assert len(txns) == 2
    assert txns[0].txn_date == date(2024, 1, 20)
    assert txns[0].amount == Decimal("38.25")
    assert txns[0].txn_type == "DEBIT"

    assert txns[1].txn_date == date(2024, 1, 22)
    assert txns[1].amount == Decimal("1800.00")
    assert txns[1].txn_type == "CREDIT"
    assert txns[1].balance == Decimal("4920.50")


def test_dutch_bank_format_extraction():
    """ING / Rabobank: Datum | Omschrijving | Af | Bij | Saldo"""
    table = [
        ["Datum", "Naam / Omschrijving", "Af", "Bij", "Saldo"],
        ["01-03-2024", "Albert Heijn Supermarkt Amsterdam", "48,75", "", "1.250,00"],
        ["02-03-2024", "Salaris Acme BV Payroll", "", "3.200,00", "4.450,00"],
        ["03-03-2024", "NS Treinkaartje Utrecht", "14,50", "", "4.435,50"],
    ]
    txns = normalize_table_rows(table, use_ml=True)
    assert len(txns) == 3
    assert txns[0].txn_date == date(2024, 3, 1)
    assert txns[0].amount == Decimal("48.75")
    assert txns[0].txn_type == "DEBIT"
    assert txns[0].category == "Groceries"

    assert txns[1].txn_date == date(2024, 3, 2)
    assert txns[1].amount == Decimal("3200.00")
    assert txns[1].txn_type == "CREDIT"
    assert txns[1].category == "Income & Salary"

    assert txns[2].txn_date == date(2024, 3, 3)
    assert txns[2].amount == Decimal("14.50")
    assert txns[2].txn_type == "DEBIT"
    assert txns[2].category == "Travel & Transport"


def test_italian_bank_format_extraction():
    """Intesa Sanpaolo: Data operazione | Descrizione operazione | Addebiti | Accrediti | Saldo"""
    table = [
        ["Data operazione", "Descrizione operazione", "Addebiti", "Accrediti", "Saldo"],
        ["10/04/2024", "Trenitalia Biglietto Roma Milano", "79,00", "", "2.100,50"],
        ["12/04/2024", "Stipendio Mensile Azienda SPA", "", "2.400,00", "4.500,50"],
    ]
    txns = normalize_table_rows(table, use_ml=True)
    assert len(txns) == 2
    assert txns[0].txn_date == date(2024, 4, 10)
    assert txns[0].amount == Decimal("79.00")
    assert txns[0].txn_type == "DEBIT"
    assert txns[0].category == "Travel & Transport"

    assert txns[1].txn_date == date(2024, 4, 12)
    assert txns[1].amount == Decimal("2400.00")
    assert txns[1].txn_type == "CREDIT"


def test_portuguese_bank_format_extraction():
    """Banco do Brasil / Caixa: Data | Historico | Debito | Credito | Saldo"""
    table = [
        ["Data", "Historico", "Debito", "Credito", "Saldo"],
        ["15/05/2024", "COMPRA FARMACIA DROGASIL", "52,30", "", "3.400,00"],
        ["16/05/2024", "TED SALARIO MENSAL", "", "4.000,00", "7.400,00"],
    ]
    txns = normalize_table_rows(table, use_ml=True)
    assert len(txns) == 2
    assert txns[0].txn_date == date(2024, 5, 15)
    assert txns[0].amount == Decimal("52.30")
    assert txns[0].txn_type == "DEBIT"

    assert txns[1].txn_date == date(2024, 5, 16)
    assert txns[1].amount == Decimal("4000.00")
    assert txns[1].txn_type == "CREDIT"


def test_polish_bank_format_extraction():
    """PKO Bank Polski: Data operacji | Opis operacji | Obciazenia | Uznania | Saldo"""
    table = [
        ["Data operacji", "Opis operacji", "Obciazenia", "Uznania", "Saldo"],
        ["05.06.2024", "BIEDRONKA ZAKUPY SPOZYWCZE", "125,50", "", "5.200,00"],
        ["06.06.2024", "WYPLATA WYNAGRODZENIE ZA PRACE", "", "6.500,00", "11.700,00"],
    ]
    txns = normalize_table_rows(table, use_ml=True)
    assert len(txns) == 2
    assert txns[0].txn_date == date(2024, 6, 5)
    assert txns[0].amount == Decimal("125.50")
    assert txns[0].txn_type == "DEBIT"

    assert txns[1].txn_date == date(2024, 6, 6)
    assert txns[1].amount == Decimal("6500.00")
    assert txns[1].txn_type == "CREDIT"


def test_australian_bank_format_and_bsb_marker():
    """Commonwealth Bank of Australia: BSB 062-000 with AUD amounts and Day-first dates where all days/months <= 12."""
    table = [
        ["Date", "Transaction Details", "Debit", "Credit", "Balance"],
        ["Account 12345678", "BSB 062-000 Statement Period Jan 2024", "", "", ""],
        ["05/01/2024", "Coles Supermarket Sydney", "$65.50", "", "$2,434.50"],
        ["06/01/2024", "Woolworths Grocery Melbourne", "$82.00", "", "$2,352.50"],
        ["07/01/2024", "Salary Payout AUD", "", "$3,500.00", "$5,852.50"],
    ]
    txns = normalize_table_rows(table, use_ml=True)
    assert len(txns) == 3
    # Confirms 5th Jan, 6th Jan, 7th Jan (not May 1st or June 1st)
    assert txns[0].txn_date == date(2024, 1, 5)
    assert txns[0].amount == Decimal("65.50")
    assert txns[0].txn_type == "DEBIT"
    assert txns[0].category == "Groceries"

    assert txns[1].txn_date == date(2024, 1, 6)
    assert txns[2].txn_date == date(2024, 1, 7)
    assert txns[2].amount == Decimal("3500.00")
    assert txns[2].txn_type == "CREDIT"


def test_us_statement_no_false_dayfirst_from_substrings():
    """Verify US statement with 'Mrs. Smith' and 'Entrepreneur Magazine' does NOT falsely trigger dayfirst."""
    table = [
        ["Date", "Description", "Amount", "Balance"],
        ["10/05/2024", "Mrs. Smith Bakery New York", "50.00", "1000.00"],
        ["10/06/2024", "Entrepreneur Magazine Subscr", "25.00", "975.00"],
        ["10/07/2024", "Pasteur Clinic Consultation", "120.00", "855.00"],
    ]
    txns = normalize_table_rows(table, use_ml=True)
    assert len(txns) == 3
    # October 5, October 6, October 7 (month-first), not May 10, June 10, July 10!
    assert txns[0].txn_date == date(2024, 10, 5)
    assert txns[1].txn_date == date(2024, 10, 6)
    assert txns[2].txn_date == date(2024, 10, 7)


def test_accounting_trailing_signs_and_swiss_apostrophes():
    """Verify trailing minus (100.00-), trailing plus (500.00+), and Swiss apostrophes (CHF 1'250.50)."""
    assert is_amount("100.00-")
    assert is_amount("1.250,50-")
    assert is_amount("500.00+")
    assert is_amount("CHF 1'250.50")
    assert is_amount("1.250.000")
    assert is_amount("1  250,50")

    amt1, hint1 = parse_amount("150.00-")
    assert amt1 == Decimal("150.00")
    assert hint1 == "DEBIT"

    amt2, hint2 = parse_amount("2.500,00-")
    assert amt2 == Decimal("2500.00")
    assert hint2 == "DEBIT"

    amt3, hint3 = parse_amount("1.000,00+")
    assert amt3 == Decimal("1000.00")
    assert hint3 == "CREDIT"

    amt4, _ = parse_amount("CHF 1'250.50")
    assert amt4 == Decimal("1250.50")

    amt5, _ = parse_amount("1  250,50")
    assert amt5 == Decimal("1250.50")

    amt6, _ = parse_amount("1.250.000")
    assert amt6 == Decimal("1250000")


def test_multilingual_named_months_and_weekday_prefix():
    """Verify parse_date handles German, French, Spanish named months and weekday prefixes."""
    assert parse_date("15-Okt-2024") == date(2024, 10, 15)
    assert parse_date("15-Dez-2024") == date(2024, 12, 15)
    assert parse_date("15-Ene-2024") == date(2024, 1, 15)
    assert parse_date("15-Dic-2024") == date(2024, 12, 15)
    assert parse_date("15-Mär-2024") == date(2024, 3, 15)
    assert parse_date("15-Févr-2024") == date(2024, 2, 15)
    assert parse_date("15-Août-2024") == date(2024, 8, 15)

    assert parse_date("Mo, 15.01.2024") == date(2024, 1, 15)
    assert parse_date("Lun 15/01/2024") == date(2024, 1, 15)
    assert parse_date("Mar. 21/01/2026") == date(2026, 1, 21)


def test_safe_table_year_extraction():
    """Verify that transactions with spend amount 2055.00 do NOT distort table_year to 2055."""
    table = [
        ["Date", "Description", "Amount", "Balance"],
        ["01/15", "Laptop Purchase", "2055.00", "5000.00"],
        ["01/16", "Coffee Shop", "5.00", "4995.00"],
    ]
    # In table without explicit row years, default_year is current year (or document year if stated), never 2055!
    txns = normalize_table_rows(table, use_ml=True)
    assert len(txns) == 2
    assert txns[0].txn_date.year != 2055
    assert txns[0].txn_date.year == date.today().year

