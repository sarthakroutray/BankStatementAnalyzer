from datetime import date
from decimal import Decimal

from app.services.normalizer import (
    classify_category,
    compute_row_hash,
    detect_column_headers,
    normalize_table_rows,
    parse_amount,
    parse_date,
)


def test_classify_category():
    assert classify_category("Starbucks Store #1234") == "Food & Dining"
    assert classify_category("CHIPOTLE ONLINE ORDER") == "Food & Dining"
    assert classify_category("Whole Foods Market") == "Groceries"
    assert classify_category("Trader Joe's groceries") == "Groceries"
    assert classify_category("PG&E ELECTRIC BILL") == "Utilities"
    assert classify_category("Comcast Xfinity Internet") == "Utilities"
    assert classify_category("UBER TRIP HELP.UBER.COM") == "Travel"
    assert classify_category("Delta Air Lines Flight") == "Travel"
    assert classify_category("NETFLIX.COM DIGITAL SUBSCRIPTION") == "Subscriptions"
    assert classify_category("SPOTIFY USA") == "Subscriptions"
    assert classify_category("Zelle payment to John") == "Transfers"
    assert classify_category("DIRECT DEPOSIT ACME CORP SALARY") == "Transfers"
    assert classify_category("Amazon.com*2A3B4C Retail") == "Shopping"
    assert classify_category("Unknown Vendor 123") == "Other"


def test_parse_date():
    assert parse_date("2024-03-15") == date(2024, 3, 15)
    assert parse_date("03/15/2024") == date(2024, 3, 15)
    assert parse_date("15-Jan-2024") == date(2024, 1, 15)
    assert parse_date("15.01.2024") == date(2024, 1, 15)
    assert parse_date("") is None
    assert parse_date("InvalidDateString") is None
    # Ensure footer/summary text with numbers are NOT mistakenly parsed as dates
    assert parse_date("Page 1 of 2") is None
    assert parse_date("Amount 12.50") is None
    assert parse_date("Account 1234") is None
    assert parse_date("Total: $500.00") is None


def test_parse_amount():
    amt, hint = parse_amount("$123.45")
    assert amt == Decimal("123.45")
    assert hint is None

    # Positive sign hints credit
    amt, hint = parse_amount("+120.00")
    assert amt == Decimal("120.00")
    assert hint == "CREDIT"

    amt, hint = parse_amount("+$500.00")
    assert amt == Decimal("500.00")
    assert hint == "CREDIT"

    amt, hint = parse_amount("45.00 CR")
    assert amt == Decimal("45.00")
    assert hint == "CREDIT"

    amt, hint = parse_amount("12.50 DR")
    assert amt == Decimal("12.50")
    assert hint == "DEBIT"

    amt, hint = parse_amount("(85.00)")
    assert amt == Decimal("85.00")
    assert hint == "DEBIT"

    amt, hint = parse_amount("-99.99")
    assert amt == Decimal("99.99")
    assert hint == "DEBIT"

    # European decimal formatting (comma as decimal, period as thousands)
    amt, hint = parse_amount("125,50")
    assert amt == Decimal("125.50")

    amt, hint = parse_amount("1.250,50")
    assert amt == Decimal("1250.50")

    assert parse_amount("") is None
    assert parse_amount("N/A") is None


def test_compute_row_hash_idempotency():
    h1 = compute_row_hash(date(2024, 1, 1), "Starbucks Coffee", Decimal("5.50"), Decimal("100.00"))
    h2 = compute_row_hash(date(2024, 1, 1), " starbucks coffee ", Decimal("5.50"), Decimal("100.00"))
    assert h1 == h2

    h3 = compute_row_hash(date(2024, 1, 1), "Starbucks Coffee", Decimal("6.50"), Decimal("100.00"))
    assert h1 != h3


def test_detect_column_headers():
    headers = ["Txn Date", "Particulars", "Debit", "Credit", "Balance"]
    mapping = detect_column_headers(headers)
    assert mapping.is_valid
    assert mapping.date_idx == 0
    assert mapping.desc_idx == 1
    assert mapping.debit_idx == 2
    assert mapping.credit_idx == 3
    assert mapping.balance_idx == 4

    # Combined Debit / Credit header
    comb_headers = ["Date", "Narration", "Debit / Credit", "Balance"]
    comb_map = detect_column_headers(comb_headers)
    assert comb_map.is_valid
    assert comb_map.amount_idx == 2
    assert comb_map.debit_idx is None
    assert comb_map.credit_idx is None


def test_normalize_table_rows():
    raw_table = [
        ["Date", "Description", "Debit", "Credit", "Balance"],
        ["2024-01-05", "Starbucks Store #442", "6.25", "", "1500.00"],
        ["2024-01-06", "Whole Foods Grocery", "78.40", "", "1421.60"],
        ["2024-01-07", "Payroll Direct Deposit", "", "2500.00", "3921.60"],
        ["2024-01-08", "Netflix Subscription", "15.99", "", "3905.61"],
    ]

    txns = normalize_table_rows(raw_table)
    assert len(txns) == 4

    assert txns[0].txn_date == date(2024, 1, 5)
    assert txns[0].amount == Decimal("6.25")
    assert txns[0].txn_type == "DEBIT"
    assert txns[0].category == "Food & Dining"
    assert txns[0].balance == Decimal("1500.00")

    assert txns[1].category == "Groceries"
    assert txns[2].txn_type == "CREDIT"
    assert txns[2].category == "Transfers"
    assert txns[3].category == "Subscriptions"
