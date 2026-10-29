"""
Self-contained transaction categorization training module.
Builds, validates, and serializes the TF-IDF + Logistic Regression category classifier
with zero custom functions inside the scikit-learn Pipeline.
"""

from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import random
from typing import Dict, List, Optional, Tuple, Union

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import FeatureUnion, Pipeline

# Shared deterministic preprocessor
try:
    from backend.app.utils.text_cleaner import clean_bank_narration
except ImportError:
    try:
        from app.utils.text_cleaner import clean_bank_narration
    except ImportError:
        import sys
        _backend_dir = Path(__file__).resolve().parent.parent
        if str(_backend_dir) not in sys.path:
            sys.path.insert(0, str(_backend_dir))
        from app.utils.text_cleaner import clean_bank_narration

logger = logging.getLogger("train_categorizer")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

CANONICAL_CATEGORIES = [
    "Food & Dining",
    "Groceries",
    "Shopping",
    "Travel & Transport",
    "Utilities & Bills",
    "Entertainment & Subscriptions",
    "EMI & Loans",
    "Investments",
    "Healthcare",
    "Income & Salary",
    "Transfers",
]

# Merchant dictionaries for synthetic bank narrations
CATEGORY_MERCHANTS: Dict[str, List[str]] = {
    "Food & Dining": [
        "Swiggy", "Zomato", "Starbucks", "Dominos Pizza", "McDonalds", "Burger King",
        "KFC", "Haldirams", "Barbeque Nation", "Rebel Foods", "EatClub", "Cafe Coffee Day",
        "Subway", "Chai Point", "Chaayos", "Pizza Hut", "Biryani By Kilo", "Faasos",
        "Baskin Robbins", "Behrouz Biryani", "Mainland China", "Theobroma",
    ],
    "Groceries": [
        "Blinkit", "Zepto", "Swiggy Instamart", "BigBasket", "DMart", "Reliance Smart",
        "Spencer's", "Nature's Basket", "Kirana Store", "Supermart", "Mother Dairy",
        "FreshToHome", "Country Delight", "Licious", "Star Bazaar", "More Supermarket",
        "Ratnadeep Supermarket", "Amul Store", "Dunzo Daily",
    ],
    "Shopping": [
        "Amazon Pay India", "AMZN MKTP", "Flipkart", "Myntra", "Ajio", "Nykaa",
        "Meesho", "Decathlon", "Croma", "Reliance Digital", "Zara", "H&M", "Uniqlo",
        "Tata Cliq", "Vijay Sales", "Shoppers Stop", "Lifestyle Store", "Westside",
        "Max Fashion", "Titan Eyeplus", "IKEA India", "Bata Shoe Store",
    ],
    "Travel & Transport": [
        "Uber India", "Ola Cabs", "Rapido Bike Taxi", "IRCTC Ticketing", "IndiGo Airlines",
        "Air India Express", "Vistara", "MakeMyTrip", "Goibibo", "RedBus",
        "HPCL Fuel", "IOCL Petrol", "BPCL Petrol Bunk", "Fastag Toll NHAI",
        "Akasa Air", "Shell Petrol Pump", "Yulu Bikes", "Chalo Bus", "Auto Rickshaw Meter",
    ],
    "Utilities & Bills": [
        "Jio Prepaid Recharge", "Jio Fiber", "Airtel Broadband", "Vi Postpaid",
        "BSNL Landline", "BESCOM Electricity", "JVVNL Power", "Tata Power DDL",
        "Adani Electricity Mumbai", "Mahanagar Gas MGL", "Indane Gas Booking",
        "BBPS BillDesk", "HP Gas Cylinder", "Bharat Gas", "ACT Fibernet",
        "BWSSB Water Supply", "Hathway Cable", "Dish TV Recharge", "Tata Play DTH",
    ],
    "Entertainment & Subscriptions": [
        "Netflix Entertainment", "Spotify India", "YouTube Premium", "Google Play Store",
        "Apple Services", "Steam Games", "Sony LIV", "Disney Hotstar",
        "BookMyShow Movie Tickets", "PVR Inox Cinemas", "Prime Video", "Zee5 Subscription",
        "Audible India", "Crunchyroll", "Sony Playstation Store", "Kindle Unlimited",
    ],
    "EMI & Loans": [
        "Bajaj Finance EMI", "HDFC Loan Auto Debit", "ICICI Personal Loan EMI",
        "NACH Mandate EMI Debit", "Cred Club Card Bill", "SBI Card Payment",
        "Home Credit Loan", "Muthoot Finance EMI", "Axis Bank Loan Debit",
        "Kotak Mahindra Loan", "Tata Capital Financial", "IDFC First Bank EMI",
        "OneCard Repayment",
    ],
    "Investments": [
        "Zerodha Broking Coin", "Groww Invest Tech", "Upstox Securities", "Angel One Broking",
        "Kuvera Mutual Fund", "IndMoney US Stocks", "Mutual Fund SIP Auto Debit",
        "Indian Clearing Corp ICCL", "NPS Trust Contribution", "HDFC Sky Broking",
        "ICICI Direct", "Motilal Oswal", "UTI Mutual Fund", "SBI Mutual Fund",
        "Mirae Asset SIP", "Nippon India MF",
    ],
    "Healthcare": [
        "Apollo Pharmacy", "PharmEasy Medicines", "Tata 1mg Healthcare", "Netmeds",
        "Thyrocare Diagnostic", "Dr Lal PathLabs", "Fortis Hospital", "Max Healthcare",
        "Practo Consultation", "Medplus Pharmacy", "Care Hospital", "Manipal Hospital",
        "SRL Diagnostics", "Metropolis Healthcare", "Wellness Forever",
    ],
    "Income & Salary": [
        "Infosys Limited Payroll", "TCS Company Payroll", "Wipro Technologies Salary",
        "Accenture Solutions Salary", "Cognizant Payroll", "HCL Tech Salary Credit",
        "Tech Mahindra Salary", "Monthly Stipend Credit", "Income Tax Refund",
        "Interest Credit Savings Account", "ACH C Dividend Payout", "Annual Performance Bonus",
        "Consulting Fee Payout", "Direct Deposit Payroll",
    ],
    "Transfers": [
        "Rahul Sharma", "Pooja Patel", "Amit Kumar", "Sneha Reddy",
        "Vikram Singh", "Ananya Iyer", "Rohan Mehta", "Priyanka Nair",
        "Suresh Raina", "Deepak Verma", "Kavita Joshi", "Manish Pandey",
        "Neha Gupta", "Arjun Rao", "Divya Menon", "Rajesh Agarwal",
        "Swati Deshmukh", "Nikhil Kulkarni", "Meera Pillai", "Gaurav Malhotra",
        "Aditya Sen", "Shreya Das", "Karthik Sundaram", "Sandhya Chawla",
        "Self Transfer", "Rent Landlord", "Roommate Split",
    ],
}

INDIAN_CITIES = [
    "Bangalore", "Bengaluru", "Mumbai", "New Delhi", "Delhi", "Gurgaon", "Gurugram",
    "Noida", "Hyderabad", "Pune", "Chennai", "Kolkata", "Ahmedabad", "Jaipur", "Kochi",
]

UPI_HANDLES = [
    "okhdfcbank", "okaxis", "okicici", "oksbi", "paytm", "ybl", "upi", "ibl", "apl", "axl",
]

BANK_IFSC_PREFIXES = ["HDFC", "ICIC", "SBIN", "UTIB", "KKBK", "PUNB", "BARB", "YESB"]


CATEGORY_ALIASES: Dict[str, str] = {
    "food & dining": "Food & Dining",
    "food and dining": "Food & Dining",
    "food": "Food & Dining",
    "dining": "Food & Dining",
    "restaurant": "Food & Dining",
    "groceries": "Groceries",
    "grocery": "Groceries",
    "supermarket": "Groceries",
    "shopping": "Shopping",
    "retail": "Shopping",
    "ecommerce": "Shopping",
    "travel & transport": "Travel & Transport",
    "travel and transport": "Travel & Transport",
    "travel": "Travel & Transport",
    "transport": "Travel & Transport",
    "transportation": "Travel & Transport",
    "utilities & bills": "Utilities & Bills",
    "utilities and bills": "Utilities & Bills",
    "utilities": "Utilities & Bills",
    "bills": "Utilities & Bills",
    "bill payments": "Utilities & Bills",
    "entertainment & subscriptions": "Entertainment & Subscriptions",
    "entertainment and subscriptions": "Entertainment & Subscriptions",
    "entertainment": "Entertainment & Subscriptions",
    "subscriptions": "Entertainment & Subscriptions",
    "subscription": "Entertainment & Subscriptions",
    "emi & loans": "EMI & Loans",
    "emi and loans": "EMI & Loans",
    "loans": "EMI & Loans",
    "loan": "EMI & Loans",
    "emi": "EMI & Loans",
    "investments": "Investments",
    "investment": "Investments",
    "mutual funds": "Investments",
    "stocks": "Investments",
    "healthcare": "Healthcare",
    "health": "Healthcare",
    "medical": "Healthcare",
    "pharmacy": "Healthcare",
    "income & salary": "Income & Salary",
    "income and salary": "Income & Salary",
    "income": "Income & Salary",
    "salary": "Income & Salary",
    "payroll": "Income & Salary",
    "transfers": "Transfers",
    "transfer": "Transfers",
    "p2p": "Transfers",
}


def generate_synthetic_bank_narrations(
    samples_per_category: Union[int, Dict[str, int]] = 700
) -> List[Tuple[str, str]]:
    """
    Generate realistic noisy Indian bank statement narrations across canonical categories.
    Simulates real payment rails: UPI, POS, ACH, NEFT, IMPS, and BBPS, incorporating
    randomized noise (UTR numbers, timestamps, city suffixes, and truncated merchant strings).
    """
    rng = random.Random(42)
    records: List[Tuple[str, str]] = []

    for category, merchants in CATEGORY_MERCHANTS.items():
        n_samples = (
            samples_per_category.get(category, 700)
            if isinstance(samples_per_category, dict)
            else samples_per_category
        )
        for _ in range(n_samples):
            merchant = rng.choice(merchants)

            # Realistic noise: truncated merchant string (simulating 12-18 char bank field limits)
            if rng.random() < 0.12 and len(merchant) > 8:
                trunc_len = rng.randint(6, len(merchant) - 1)
                truncated = merchant[:trunc_len].strip()
                if truncated.lower() != "swiggy":
                    merchant = truncated

            city = rng.choice(INDIAN_CITIES)
            handle = rng.choice(UPI_HANDLES)
            utr = rng.randint(100000000000, 999999999999)
            ref_num = rng.randint(100000, 99999999)

            # Masked card variations: XX1234, XXXX 1234, 4591XXXXXXXX1234
            card_variant = rng.choice(["short", "spaced", "bin_masked"])
            if card_variant == "short":
                card_mask = f"XX{rng.randint(1000, 9999)}"
            elif card_variant == "spaced":
                card_mask = f"XXXX {rng.randint(1000, 9999)}"
            else:
                bin_prefix = rng.choice(["4591", "4111", "5241", "6071"])
                card_mask = f"{bin_prefix}XXXXXXXX{rng.randint(1000, 9999)}"

            ifsc = f"{rng.choice(BANK_IFSC_PREFIXES)}0{rng.randint(100000, 999999)}"
            day = rng.randint(1, 28)
            month = rng.randint(1, 12)
            year = rng.choice([2023, 2024, 2025])
            date_str = f"{day:02d}/{month:02d}/{year}"

            # Timestamp noise (e.g. 14:23:05 or 09:45)
            hour = rng.randint(0, 23)
            minute = rng.randint(0, 59)
            second = rng.randint(0, 59)
            time_str = f"{hour:02d}:{minute:02d}:{second:02d}" if rng.random() < 0.5 else f"{hour:02d}:{minute:02d}"

            # Variations depending on category
            if category == "Income & Salary":
                template_type = rng.choice([
                    "NEFT_SALARY", "ACH_SALARY", "STIPEND", "DIVIDEND",
                    "TAX_REFUND", "INTEREST", "PAYROLL_DD"
                ])
                if template_type == "NEFT_SALARY":
                    text = f"NEFT CR-{ifsc}-{merchant}-SALARY CREDIT FOR {month:02d}/{year}-{ref_num} {time_str}"
                elif template_type == "ACH_SALARY":
                    text = f"ACH C- {merchant} - MONTHLY SALARY CREDIT {ref_num} {date_str}"
                elif template_type == "STIPEND":
                    text = f"NEFT CR-{ifsc}-STIPEND CREDIT {merchant}-{ref_num}"
                elif template_type == "DIVIDEND":
                    text = f"ACH C- DIVIDEND PAYOUT {merchant} REF {ref_num}"
                elif template_type == "TAX_REFUND":
                    text = f"NEFT CR-INCOME TAX REFUND-REF{ref_num}-{ifsc}"
                elif template_type == "INTEREST":
                    text = f"INTEREST CREDIT FOR Q{rng.randint(1, 4)} FY{year % 100}-{(year % 100) + 1}"
                else:
                    text = f"DIRECT DEPOSIT {merchant} SALARY {ref_num} {date_str}"

            elif category == "Transfers":
                template_type = rng.choice([
                    "UPI_P2P", "IMPS_P2A", "SELF_XFER", "FAMILY_NEFT", "RENT_XFER"
                ])
                if template_type == "UPI_P2P":
                    p2p_tag = rng.choice(["p2p", "payment", "transfer", "split"])
                    clean_m = merchant.lower().replace(" ", "")
                    text = f"UPI/{utr}/{merchant}/{clean_m}@{handle}/{p2p_tag} {time_str}"
                elif template_type == "IMPS_P2A":
                    text = f"IMPS P2A/{utr}/{merchant}/TRANSFER {ref_num} {time_str}"
                elif template_type == "SELF_XFER":
                    text = f"SELF TRANSFER TO SAVINGS ACC {ref_num} {ifsc}"
                elif template_type == "FAMILY_NEFT":
                    text = f"NEFT DR-{ifsc}-{merchant}-FAMILY TRANSFER {ref_num}"
                else:
                    text = f"UPI/{utr}/RENT PAYMENT TO {merchant.upper()}/{handle}"

            elif category == "Utilities & Bills":
                rail = rng.choice(["BBPS", "UPI", "ACH", "DIRECT"])
                if rail == "BBPS":
                    text = f"BBPS/{merchant}/BILLDESK/{ref_num}/{date_str}"
                elif rail == "UPI":
                    text = f"UPI/{utr}/{merchant.replace(' ', '')}@{handle}/BILLPAY {time_str}"
                elif rail == "ACH":
                    text = f"ACH D- {merchant} {ref_num}"
                else:
                    text = f"{merchant} BILL PAYMENT {city} REF-{ref_num}"

            elif category == "EMI & Loans":
                rail = rng.choice(["NACH", "ACH", "AUTO_DEBIT", "UPI"])
                if rail == "NACH":
                    text = f"NACH MANDATE EMI DEBIT - {merchant} - {ref_num}"
                elif rail == "ACH":
                    text = f"ACH D- {merchant} {ref_num}"
                elif rail == "AUTO_DEBIT":
                    text = f"AUTO DEBIT LOAN EMI {merchant} {card_mask} {ref_num}"
                else:
                    text = f"UPI/{utr}/{merchant.replace(' ', '')}@{handle}/LOAN REPAYMENT"

            elif category == "Investments":
                rail = rng.choice(["UPI", "ACH", "NETBANKING", "SIP"])
                if rail == "SIP":
                    text = f"ACH D- MUTUAL FUND SIP {merchant} {ref_num}"
                elif rail == "UPI":
                    text = f"UPI/{utr}/{merchant.replace(' ', '')}@{handle}/INVEST"
                elif rail == "ACH":
                    text = f"ACH D- {merchant} {ref_num}"
                else:
                    text = f"INDIAN CLEARING CORP ICCL - {merchant} - {ref_num}"

            else:
                # General categories: Food & Dining, Groceries, Shopping, Travel & Transport,
                # Entertainment & Subscriptions, Healthcare
                rail = rng.choice(["UPI", "POS", "BBPS", "PLAIN", "ORDER", "ONLINE"])
                if rail == "UPI":
                    text = f"UPI/{utr}/{merchant.replace(' ', '')}@{handle}/payment for order {ref_num}"
                elif rail == "POS":
                    text = f"POS {card_mask} {merchant.upper()} {city} {date_str} {time_str}"
                elif rail == "BBPS":
                    text = f"BBPS/{merchant.upper()}/{ref_num}"
                elif rail == "ORDER":
                    text = f"{merchant} {city} Order {ref_num}"
                elif rail == "ONLINE":
                    text = f"{merchant} ONLINE {city} REF {ref_num}"
                else:
                    text = f"POS TXN {card_mask} {merchant} {city} REF {ref_num}"

            records.append((text, category))

    rng.shuffle(records)
    return records


def load_dataset(csv_path: Optional[str] = None, include_archive: bool = True) -> pd.DataFrame:
    """
    Load transactions from CSV if present, harmonizing columns, and merge with
    synthetic Indian banking narrations.

    Automatically scans and ingests actual archive CSVs (e.g. financial_transaction_train.csv
    and financial_transaction_test.csv in backend/ml/archive) and data directory CSVs.
    """
    dfs: List[pd.DataFrame] = []
    seen_files = set()
    loaded_sources: List[str] = []

    candidate_paths: List[Path] = []
    if csv_path:
        p = Path(csv_path)
        if p.exists() and p.is_file():
            candidate_paths.append(p)
        elif p.exists() and p.is_dir():
            candidate_paths.extend(sorted(p.glob("*.csv")))

    if include_archive:
        current_dir = Path(__file__).resolve().parent
        # Archive directory: backend/ml/archive
        archive_dir = current_dir / "archive"
        if archive_dir.exists():
            candidate_paths.extend(sorted(archive_dir.glob("*.csv")))

        # Data directory: backend/ml/data
        data_dir = current_dir / "data"
        if data_dir.exists():
            candidate_paths.extend(sorted(data_dir.glob("*.csv")))

    for file_path in candidate_paths:
        resolved = file_path.resolve()
        if resolved in seen_files:
            continue
        seen_files.add(resolved)

        try:
            raw_df = pd.read_csv(resolved)
            # Find description / narration column
            desc_col = None
            for col in [
                "Transaction_Text",
                "transaction_text",
                "Description",
                "description",
                "narration",
                "Narration",
                "text",
                "Text",
            ]:
                if col in raw_df.columns:
                    desc_col = col
                    break

            cat_col = None
            for col in [
                "Label",
                "label",
                "Category",
                "category",
                "target",
                "Target",
            ]:
                if col in raw_df.columns:
                    cat_col = col
                    break

            if desc_col and cat_col:
                subset = raw_df[[desc_col, cat_col]].dropna().copy()
                subset.columns = ["text", "category"]
                # Harmonize category names using canonical set and alias dictionary
                harmonized_cats = []
                for val in subset["category"]:
                    clean_val = str(val).strip().lower()
                    if clean_val in CATEGORY_ALIASES:
                        harmonized_cats.append(CATEGORY_ALIASES[clean_val])
                    elif str(val).strip() in CANONICAL_CATEGORIES:
                        harmonized_cats.append(str(val).strip())
                    else:
                        harmonized_cats.append(None)
                subset["category"] = harmonized_cats
                subset = subset.dropna(subset=["category"])
                if not subset.empty:
                    dfs.append(subset)
                    loaded_sources.append(resolved.name)
                    logger.info("Loaded and harmonized %d records from CSV %s", len(subset), resolved)
        except Exception as ex:
            logger.warning("Could not ingest CSV %s: %s", resolved, ex)

    # Balance dataset: if external/archive CSVs provided records for specific categories
    # (e.g. Food, Travel, Shopping, Investments, EMI), generate 800 synthetic samples for rail coverage,
    # and 2,500 synthetic samples for categories not covered in the CSVs (Groceries, Utilities, etc.)
    archive_cats = set()
    for d in dfs:
        archive_cats.update(d["category"].unique())

    if archive_cats:
        synth_counts: Dict[str, int] = {}
        for cat in CANONICAL_CATEGORIES:
            synth_counts[cat] = 800 if cat in archive_cats else 2500
        synth_records = generate_synthetic_bank_narrations(samples_per_category=synth_counts)
    else:
        synth_records = generate_synthetic_bank_narrations(samples_per_category=800)

    synth_df = pd.DataFrame(synth_records, columns=["text", "category"])
    logger.info("Generated %d synthetic Indian banking narrations", len(synth_df))
    dfs.append(synth_df)

    combined = pd.concat(dfs, ignore_index=True)
    return combined


def build_pipeline() -> Pipeline:
    """
    Build scikit-learn TF-IDF + Logistic Regression pipeline.
    Uses zero custom functions pickled inside the pipeline.
    """
    word_tfidf = TfidfVectorizer(
        ngram_range=(1, 2),
        max_features=20000,
        sublinear_tf=True,
    )
    char_tfidf = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(3, 5),
        max_features=25000,
        sublinear_tf=True,
    )
    features = FeatureUnion([
        ("word_tfidf", word_tfidf),
        ("char_tfidf", char_tfidf),
    ])
    classifier = LogisticRegression(
        C=2.5,
        max_iter=1000,
        class_weight="balanced",
        random_state=42,
    )
    pipeline = Pipeline([
        ("features", features),
        ("classifier", classifier),
    ])
    return pipeline


def resolve_default_paths() -> Tuple[Path, Path, Path]:
    """Resolve default paths relative to workspace or backend directory."""
    current_dir = Path(__file__).resolve().parent  # backend/ml
    backend_dir = current_dir.parent               # backend
    project_root = backend_dir.parent              # workspace root

    # Model artifact path
    model_path = backend_dir / "ml" / "artifacts" / "category_classifier.joblib"
    metadata_path = backend_dir / "ml" / "artifacts" / "model_metadata.json"
    data_csv_path = backend_dir / "ml" / "data" / "transactions.csv"

    return model_path, metadata_path, data_csv_path


def train_and_save_model(
    data_csv_path: Optional[str] = None,
    model_path: Optional[str] = None,
    metadata_path: Optional[str] = None,
    random_state: int = 42,
) -> Pipeline:
    """
    Train category classifier and serialize artifact and metadata.
    """
    env_model_path = os.getenv("CATEGORY_MODEL_PATH")
    if not model_path and env_model_path:
        model_path = env_model_path

    def_model, def_meta, def_csv = resolve_default_paths()
    target_model_path = Path(model_path) if model_path else def_model
    if metadata_path:
        target_meta_path = Path(metadata_path)
    elif model_path:
        target_meta_path = Path(model_path).parent / "model_metadata.json"
    else:
        target_meta_path = def_meta
    target_csv_path = str(data_csv_path) if data_csv_path else str(def_csv)

    target_model_path.parent.mkdir(parents=True, exist_ok=True)
    target_meta_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Loading / generating dataset...")
    df = load_dataset(target_csv_path)

    # Clean text deterministically before feeding into scikit-learn pipeline
    logger.info("Cleaning %d narrations with clean_bank_narration...", len(df))
    cleaned_texts = [clean_bank_narration(t) for t in df["text"]]
    labels = df["category"].tolist()

    logger.info("Splitting dataset 85/15 stratified...")
    X_train, X_val, y_train, y_val = train_test_split(
        cleaned_texts,
        labels,
        test_size=0.15,
        stratify=labels,
        random_state=random_state,
    )

    logger.info("Building scikit-learn pipeline...")
    pipeline = build_pipeline()

    logger.info("Training pipeline on %d samples...", len(X_train))
    pipeline.fit(X_train, y_train)

    logger.info("Evaluating on %d validation samples...", len(X_val))
    y_pred = pipeline.predict(X_val)
    val_f1 = float(f1_score(y_val, y_pred, average="weighted"))
    report = classification_report(y_val, y_pred)
    logger.info("Validation Weighted F1: %.4f\n%s", val_f1, report)

    # Serialize with joblib compress=3
    logger.info("Serializing model to %s...", target_model_path)
    joblib.dump(pipeline, target_model_path, compress=3)

    # Serialize metadata
    metadata = {
        "sklearn_version": sklearn.__version__,
        "classes": pipeline.classes_.tolist(),
        "validation_f1": round(val_f1, 4),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "num_samples": len(df),
        "num_train": len(X_train),
        "num_val": len(X_val),
    }
    with open(target_meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    logger.info("Wrote model metadata to %s", target_meta_path)

    return pipeline


if __name__ == "__main__":
    train_and_save_model()
