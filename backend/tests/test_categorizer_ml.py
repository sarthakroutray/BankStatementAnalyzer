import os
import pytest
from app.utils.text_cleaner import clean_bank_narration
from app.services.normalizer import (
    CategorizationResult,
    categorize_transactions_batch,
    get_category_pipeline,
    normalize_table_rows,
)
from app.schemas import TransactionCreate, TransactionRead, TransactionResponse
from app.models import Transaction


def test_clean_bank_narration():
    # 1. Dates
    assert clean_bank_narration("TXN ON 15/03/2024 COMPLETED") == "txn on completed"
    assert clean_bank_narration("TXN 01-12-23 PAID") == "txn paid"

    # 2. IFSC codes
    assert clean_bank_narration("NEFT HDFC0001234 TRANSFER") == "neft transfer"
    assert clean_bank_narration("RTGS SBIN0048192 REF") == "rtgs ref"

    # 3. 6+ digit numbers (UTRs, ref numbers)
    assert clean_bank_narration("UPI 409823482390 ORDER") == "upi order"
    assert clean_bank_narration("REF 123456789 OK") == "ref ok"
    # Small numbers (less than 6 digits) should not be stripped
    assert "123" in clean_bank_narration("STORE 123")

    # 4. Masked cards (with and without card bin prefixes)
    assert clean_bank_narration("POS XX1234 SHOP") == "pos shop"
    assert clean_bank_narration("POS XXXX5678 MART") == "pos mart"
    assert clean_bank_narration("POS 4591XXXXXXXX1234 SWIGGY") == "pos swiggy"
    assert clean_bank_narration("POS 4111xx1234 BLINKIT") == "pos blinkit"

    # 5. UPI handles
    assert clean_bank_narration("PAID TO swiggy@okhdfcbank NOW") == "paid to swiggy now"
    assert clean_bank_narration("merchant@paytm TXN") == "merchant txn"

    # 6. Delimiters, NaN, & whitespace
    assert clean_bank_narration("UPI/409823482390/swiggy@okhdfcbank/payment") == "upi swiggy payment"
    assert clean_bank_narration("ACH D- [NETFLIX] *9928341: BILL") == "ach d netflix bill"
    assert clean_bank_narration("") == ""
    assert clean_bank_narration(None) == ""
    assert clean_bank_narration(float("nan")) == ""
    assert clean_bank_narration("nan") == ""


def test_get_category_pipeline():
    pipeline = get_category_pipeline()
    assert pipeline is not None
    assert hasattr(pipeline, "predict_proba")
    assert hasattr(pipeline, "classes_")
    assert len(pipeline.classes_) == 11
    # Verify singleton lru_cache
    pipeline_again = get_category_pipeline()
    assert pipeline is pipeline_again


def test_categorize_transactions_batch_smoke_samples():
    sample_narrations = [
        "UPI/409823482390/swiggy@okhdfcbank/payment for order 12849",
        "POS XX4829 BLINKIT COMMERCE BANGALORE 15/03/2024",
        "NEFT CR-HDFC0001234-INFOSYS LIMITED-SALARY FOR MARCH 2024",
        "ACH D- NETFLIX ENTERTAINMENT 9928341",
        "BBPS/AIRTEL BROADBAND/BILLDESK/9823472910",
    ]
    sample_types = ["DEBIT", "DEBIT", "CREDIT", "DEBIT", "DEBIT"]

    results = categorize_transactions_batch(sample_narrations, sample_types)
    assert len(results) == 5

    # Swiggy -> Food & Dining
    assert results[0].category == "Food & Dining"
    assert results[0].confidence >= 0.55
    assert results[0].source == "ML_JOBLIB"

    # Blinkit -> Groceries
    assert results[1].category == "Groceries"
    assert results[1].confidence >= 0.55
    assert results[1].source == "ML_JOBLIB"

    # Infosys Salary (CREDIT) -> Income & Salary via Tier 1 Credit Guardrail
    assert results[2].category == "Income & Salary"
    assert results[2].confidence == 1.0
    assert results[2].source == "RULE_CREDIT"

    # Netflix -> Entertainment & Subscriptions
    assert results[3].category == "Entertainment & Subscriptions"
    assert results[3].confidence >= 0.55
    assert results[3].source == "ML_JOBLIB"

    # Airtel Broadband -> Utilities & Bills
    assert results[4].category == "Utilities & Bills"
    assert results[4].confidence >= 0.55
    assert results[4].source == "ML_JOBLIB"


def test_tier1_credit_guardrail():
    credits = [
        ("Monthly Stipend Credit From Lab", "CREDIT"),
        ("TCS Company Payroll Direct Deposit", "CR"),
        ("ACH C- Dividend Payout Reliance", "DEP"),
        ("Interest Credit for Savings Account", "DEPOSIT"),
        ("Income Tax Refund Dept of Revenue", "CREDIT"),
    ]
    descriptions = [c[0] for c in credits]
    types = [c[1] for c in credits]

    results = categorize_transactions_batch(descriptions, types)
    for r in results:
        assert r.category == "Income & Salary"
        assert r.confidence == 1.0
        assert r.source == "RULE_CREDIT"


def test_tier2_ml_coverage():
    test_cases = [
        ("Uber India Ride Bangalore", "DEBIT", "Travel & Transport"),
        ("Zomato Online Food Delivery", "DEBIT", "Food & Dining"),
        ("Amazon Pay India Retail Purchase", "DEBIT", "Shopping"),
        ("Bajaj Finance Loan EMI Auto Debit", "DEBIT", "EMI & Loans"),
        ("Zerodha Broking Coin SIP Fund", "DEBIT", "Investments"),
        ("Apollo Pharmacy Medicine", "DEBIT", "Healthcare"),
        ("UPI/309482910492/Rahul Sharma/rahul@okicici/p2p", "DEBIT", "Transfers"),
    ]
    descs = [t[0] for t in test_cases]
    types = [t[1] for t in test_cases]
    results = categorize_transactions_batch(descs, types)

    for i, (_, _, expected_cat) in enumerate(test_cases):
        assert results[i].category == expected_cat
        assert results[i].confidence >= 0.55
        assert results[i].source == "ML_JOBLIB"


def test_tier3_regex_and_other_fallback():
    # 1. Regex fallback with canonical categories
    test_fallbacks = [
        ("unknown electric power bill ref 998877", "Utilities & Bills"),
        ("some random auto debit loan emi 123", "EMI & Loans"),
        ("unrecognized pharmacy hospital clinic 5544", "Healthcare"),
        ("obscure broking stocks demat 1122", "Investments"),
    ]
    fb_descs = [t[0] for t in test_fallbacks]
    fb_results = categorize_transactions_batch(fb_descs, ["DEBIT"] * len(fb_descs))
    for res, (_, expected_cat) in zip(fb_results, test_fallbacks):
        assert res.category == expected_cat

    # 2. Pure unknown gibberish falls back to "Other" with REGEX_FALLBACK source
    unknown = ["xyz gibberish 999 111", "qzwkjv 789 456"]
    results = categorize_transactions_batch(unknown, ["DEBIT", "DEBIT"])
    assert len(results) == 2
    assert results[0].category == "Other"
    assert results[0].source == "REGEX_FALLBACK"
    assert results[1].category == "Other"
    assert results[1].source == "REGEX_FALLBACK"


def test_empty_and_edge_cases():
    assert categorize_transactions_batch([]) == []
    res = categorize_transactions_batch(["", None, float("nan")])
    assert len(res) == 3
    assert all(r.category == "Other" for r in res)
    assert all(r.source == "REGEX_FALLBACK" for r in res)


def test_normalize_table_rows_with_ml():
    raw_table = [
        ["Date", "Description", "Debit", "Credit", "Balance"],
        ["2024-03-01", "Swiggy Bangalore Order", "350.00", "", "10000.00"],
        ["2024-03-02", "Monthly Salary Credit", "", "75000.00", "85000.00"],
        ["2024-03-03", "Netflix Subscription", "499.00", "", "84501.00"],
    ]
    # use_ml=True
    txns = normalize_table_rows(raw_table, use_ml=True)
    assert len(txns) == 3

    assert txns[0].category == "Food & Dining"
    assert txns[0].category_source == "ML_JOBLIB"
    assert txns[0].category_confidence is not None

    assert txns[1].category == "Income & Salary"
    assert txns[1].category_source == "RULE_CREDIT"
    assert txns[1].category_confidence == 1.0

    assert txns[2].category == "Entertainment & Subscriptions"
    assert txns[2].category_source == "ML_JOBLIB"


def test_schema_and_models_compatibility():
    # TransactionResponse alias
    assert TransactionResponse is TransactionRead

    # Verify category_confidence and category_source in model fields
    assert hasattr(Transaction, "category_confidence")
    assert hasattr(Transaction, "category_source")
    assert "category_confidence" in TransactionCreate.model_fields
    assert "category_source" in TransactionCreate.model_fields
    assert "category_confidence" in TransactionRead.model_fields
    assert "category_source" in TransactionRead.model_fields


def test_load_dataset_csv_harmonization(tmp_path):
    import pandas as pd
    from ml.train_categorizer import CANONICAL_CATEGORIES, load_dataset

    # Create dummy external CSV with non-canonical aliases and varied headers
    csv_file = tmp_path / "custom_transactions.csv"
    dummy_data = pd.DataFrame({
        "Transaction_Text": [
            "Zomato Food Delivery",
            "Electricity Bill Power",
            "Uber Ride Airport",
            "Monthly salary credited",
        ],
        "Category": [
            "Food and Dining",
            "Utilities",
            "Travel",
            "Salary",
        ],
    })
    dummy_data.to_csv(csv_file, index=False)

    loaded_df = load_dataset(str(csv_file))
    assert len(loaded_df) > 5000  # Combined synthetic + CSV
    # Verify all categories belong to CANONICAL_CATEGORIES
    unique_cats = set(loaded_df["category"].unique())
    assert unique_cats.issubset(set(CANONICAL_CATEGORIES))


def test_self_healing_loader(tmp_path, monkeypatch):
    # Test that get_category_pipeline automatically trains if model is absent
    target_joblib = tmp_path / "custom_model.joblib"
    monkeypatch.setenv("CATEGORY_MODEL_PATH", str(target_joblib))

    get_category_pipeline.cache_clear()
    pipeline = get_category_pipeline()

    assert pipeline is not None
    assert target_joblib.exists()
    assert (tmp_path / "model_metadata.json").exists()

    # Clear cache and restore for subsequent tests
    get_category_pipeline.cache_clear()


