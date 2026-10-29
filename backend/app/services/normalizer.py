import functools
import hashlib
import math
import os
from pathlib import Path
import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, NamedTuple, Optional, Tuple
from dateutil import parser as date_parser
import joblib
import numpy as np

from app.schemas import TransactionCreate

try:
    from app.utils.text_cleaner import clean_bank_narration
except ImportError:
    try:
        from backend.app.utils.text_cleaner import clean_bank_narration
    except ImportError:
        import sys
        _backend_dir = Path(__file__).resolve().parent.parent.parent
        if str(_backend_dir) not in sys.path:
            sys.path.insert(0, str(_backend_dir))
        from app.utils.text_cleaner import clean_bank_narration


class CategorizationResult(NamedTuple):
    category: str
    confidence: float
    source: str


MULTILINGUAL_MONTH_MAP: Dict[str, int] = {
    # English
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
    # German
    "januar": 1,
    "februar": 2,
    "marz": 3, "maerz": 3,
    "mai": 5,
    "juni": 6,
    "juli": 7,
    "okt": 10, "oktober": 10,
    "dez": 12, "dezember": 12,
    # Spanish
    "ene": 1, "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abr": 4, "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "ago": 8, "agosto": 8,
    "set": 9, "setiembre": 9, "septiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "dic": 12, "diciembre": 12,
    # French
    "janv": 1, "janvier": 1,
    "fevr": 2, "fevrier": 2,
    "mars": 3,
    "avril": 4, "avr": 4,
    "juin": 6,
    "juil": 7, "juillet": 7,
    "aout": 8,
    "decembre": 12,
    # Italian
    "gen": 1, "gennaio": 1,
    "aprile": 4,
    "maggio": 5, "mag": 5,
    "giugno": 6, "giu": 6,
    "luglio": 7, "lug": 7,
    "ott": 10, "ottobre": 10,
    # Dutch
    "mrt": 3, "maart": 3,
    "mei": 5,
    # Portuguese
    "out": 10, "outubro": 10,
}

MONTH_NUM_TO_ENG: Dict[int, str] = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}

WEEKDAY_PREFIX_PATTERN = re.compile(
    r"^(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"mardi|mercredi|jeudi|vendredi|samedi|dimanche|"
    r"lunes|martes|miercoles|jueves|viernes|sabado|domingo|"
    r"montag|dienstag|mittwoch|donnerstag|freitag|samstag|sonntag|"
    r"mon|tue|wed|thu|fri|sat|sun|"
    r"lun|mer|jeu|ven|sam|dim|mie|jue|vie|sab|dom|seg|ter|qua|qui|sex|"
    r"mo|di|mi|do|fr|sa|so)[\.,]?\s+|^mar[\.,]\s+",
    re.IGNORECASE,
)


def normalize_multilingual_date_string(s: str) -> str:
    """Strip weekday prefixes and normalize non-English month names to 3-letter English equivalents."""
    norm = unicodedata.normalize("NFKD", s).encode("ASCII", "ignore").decode("utf-8")
    cleaned = WEEKDAY_PREFIX_PATTERN.sub("", norm).strip()

    def repl_month(m: re.Match) -> str:
        tok = m.group(0).lower()
        if tok in MULTILINGUAL_MONTH_MAP:
            return MONTH_NUM_TO_ENG[MULTILINGUAL_MONTH_MAP[tok]]
        return m.group(0)

    return re.sub(r"[A-Za-z]+", repl_month, cleaned)


CREDIT_GUARDRAIL_PATTERN = re.compile(
    r"\b(salary|stipend|dividend|interest|refund|payroll)\b",
    re.IGNORECASE,
)

LEGACY_TO_CANONICAL: Dict[str, str] = {
    "Utilities": "Utilities & Bills",
    "Travel": "Travel & Transport",
    "Subscriptions": "Entertainment & Subscriptions",
}

CANONICAL_FALLBACK_RULES: List[Tuple[str, re.Pattern]] = [
    (
        "Income & Salary",
        re.compile(
            r"\b(salary|stipend|dividend|interest\s*credit|tax\s*refund|payroll|bonus|direct\s*deposit)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Food & Dining",
        re.compile(
            r"\b(starbucks|mcdonald|chipotle|wendy|dunkin|subway|taco\s*bell|panera|"
            r"restaurant|cafe|coffee|bistro|diner|eatery|pizza|burger|sushi|bakery|"
            r"bar|pub|grill|brew|uber\s*eats|doordash|grubhub|swiggy|zomato|dominos|kfc|"
            r"just\s*eat|deliveroo|greggs|pret\s*a\s*manger|wetherspoon|"
            r"haldiram|barbeque\s*nation|eatclub|chaayos|dining)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Groceries",
        re.compile(
            r"\b(whole\s*foods|trader\s*joe|safeway|kroger|walmart|target|costco|aldi|"
            r"heb|wegmans|publix|grocer|supermarket|market|sprouts|fresh\s*market|"
            r"carrefour|mercadona|rewe|edeka|lidl|tesco|sainsbury|asda|morrisons|waitrose|"
            r"woolworths|coles|albert\s*heijn|jumbo|migros|coop|"
            r"blinkit|zepto|instamart|bigbasket|dmart|reliance\s*smart|spencer|kirana|mother\s*dairy)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Utilities & Bills",
        re.compile(
            r"\b(electric|water|gas|pge|coned|comed|internet|comcast|xfinity|verizon|"
            r"at&t|att|t-mobile|spectrum|utility|power|energy|sewer|trash|phone|broadband|"
            r"edf|engie|e\.on|eon|iberdrola|enel|vodafone|o2|orange|bt\s*group|telstra|"
            r"jio|airtel|vi\s*postpaid|bsnl|bescom|jvvnl|tata\s*power|adani|billdesk|bbps|cylinder|dth)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Travel & Transport",
        re.compile(
            r"\b(uber|lyft|flight|airline|delta|united|american\s*air|southwest|jetblue|"
            r"hotel|marriott|hilton|airbnb|vrbo|expedia|booking\.com|transit|train|amtrak|"
            r"metro|toll|parking|gas\s*station|shell|chevron|bp|exxon|mobil|speedway|"
            r"sncf|deutsche\s*bahn|db\s*fahrkarte|renfe|trenitalia|sbb|ns|oyster|eurostar|"
            r"ryanair|easyjet|lufthansa|air\s*france|british\s*airways|iberia|qantas|air\s*canada|"
            r"ola|rapido|irctc|indigo|vistara|makemytrip|goibibo|redbus|hpcl|iocl|bpcl|fastag|petrol|fuel|tfl|transport|underground|railway|rail)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Entertainment & Subscriptions",
        re.compile(
            r"\b(netflix|spotify|apple|google\s*storage|google\s*one|amazon\s*prime|"
            r"hulu|disney|hbo|max|nytimes|wsj|patreon|substack|github|openai|chatgpt|"
            r"midjourney|software|subscr|adobe|dropbox|youtube|steam|sony\s*liv|hotstar|bookmyshow|pvr|inox|zee5)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "EMI & Loans",
        re.compile(
            r"\b(emi|loan|auto\s*debit|nach\s*mandate|bajaj\s*fin|card\s*payment|card\s*bill|"
            r"home\s*credit|muthoot|repayment|mortgage)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Investments",
        re.compile(
            r"\b(zerodha|groww|upstox|angel\s*one|kuvera|indmoney|mutual\s*fund|sip|"
            r"clearing\s*corp|iccl|nps\s*trust|securities|broking|stocks|shares|demat)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Healthcare",
        re.compile(
            r"\b(apollo\s*pharmacy|pharmeasy|tata\s*1mg|netmeds|thyrocare|lal\s*pathlabs|"
            r"fortis|max\s*healthcare|practo|pharmacy|hospital|clinic|doctor|medicines|diagnostic)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Shopping",
        re.compile(
            r"\b(amazon|ebay|best\s*buy|apple\s*store|ikea|home\s*depot|lowes|zara|"
            r"h&m|nordstrom|macys|nike|adidas|clothing|retail|shop|store|boutique|mall|"
            r"flipkart|myntra|ajio|nykaa|meesho|decathlon|croma|reliance\s*digital|uniqlo)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Transfers",
        re.compile(
            r"\b(transfer|zelle|venmo|wire|ach|paypal|cash\s*app|payout|internal\s*xfer|"
            r"atm\s*withdrawal|atm\s*deposit|xfer|upi|p2p|p2a|neft|rtgs|imps|rent)\b",
            re.IGNORECASE,
        ),
    ),
]


def classify_canonical_regex(text: Any) -> Optional[str]:
    """Evaluate deterministic regex rules for the 11 canonical categories."""
    if text is None or (isinstance(text, float) and math.isnan(text)):
        return None
    raw_lower = str(text).strip().lower()
    if raw_lower in ("nan", "none", "null", ""):
        return None
    for cat, pattern in CANONICAL_FALLBACK_RULES:
        if pattern.search(raw_lower):
            return cat
    legacy = classify_category(text)
    if legacy != "Other":
        return LEGACY_TO_CANONICAL.get(legacy, legacy)
    return None


@functools.lru_cache(maxsize=1)
def get_category_pipeline():
    """
    Singleton cached loader for category classifier pipeline.
    Self-heals by running train_and_save_model() if artifact is missing.
    """
    model_path_env = os.getenv("CATEGORY_MODEL_PATH", "backend/ml/artifacts/category_classifier.joblib")
    model_path = Path(model_path_env)
    if not model_path.is_absolute():
        if not model_path.exists():
            backend_dir = Path(__file__).resolve().parent.parent.parent
            cand1 = backend_dir / model_path_env.removeprefix("backend/")
            cand2 = backend_dir.parent / model_path_env
            if cand1.exists():
                model_path = cand1
            elif cand2.exists():
                model_path = cand2
            else:
                model_path = cand1
    if not model_path.exists():
        try:
            from backend.ml.train_categorizer import train_and_save_model
        except ImportError:
            try:
                from ml.train_categorizer import train_and_save_model
            except ImportError:
                import sys
                backend_dir = Path(__file__).resolve().parent.parent.parent
                for p in [str(backend_dir), str(backend_dir.parent)]:
                    if p not in sys.path:
                        sys.path.insert(0, p)
                from ml.train_categorizer import train_and_save_model
        train_and_save_model(model_path=str(model_path))
    return joblib.load(str(model_path))


def categorize_transactions_batch(
    descriptions: List[str],
    txn_types: Optional[List[str]] = None,
) -> List[CategorizationResult]:
    """
    Vectorized batch categorizer executing 3-tier decision policy:
    - Tier 1 (Credit Guardrail): If txn_type == "CREDIT" (or CR/DEP) and matches salary/stipend/etc. -> "Income & Salary"
    - Tier 2 (High-Confidence ML): If max_prob >= 0.55 -> assign ML predicted class
    - Tier 3 (Low-Confidence Fallback): If max_prob < 0.55 -> regex fallback or "Other"
    """
    if not descriptions:
        return []

    if txn_types is None:
        txn_types = ["DEBIT"] * len(descriptions)
    elif len(txn_types) < len(descriptions):
        txn_types = list(txn_types) + ["DEBIT"] * (len(descriptions) - len(txn_types))

    pipeline = get_category_pipeline()
    cleaned = [clean_bank_narration(d) for d in descriptions]
    probs = pipeline.predict_proba(cleaned)
    classes = pipeline.classes_

    results: List[CategorizationResult] = []

    for i, (raw_desc, clean_desc, t_type) in enumerate(zip(descriptions, cleaned, txn_types)):
        norm_type = (t_type or "DEBIT").strip().upper()

        # Tier 1 (Credit Guardrail): If txn_type == "CREDIT" (or CR/DEP) and narration matches patterns
        if norm_type in ("CREDIT", "CR", "DEP", "DEPOSIT") and (
            CREDIT_GUARDRAIL_PATTERN.search(raw_desc or "")
            or CREDIT_GUARDRAIL_PATTERN.search(clean_desc or "")
        ):
            results.append(
                CategorizationResult(
                    category="Income & Salary",
                    confidence=1.0,
                    source="RULE_CREDIT",
                )
            )
            continue

        max_idx = int(np.argmax(probs[i]))
        max_prob = float(probs[i][max_idx])
        pred_class = str(classes[max_idx])

        # Tier 2 (High-Confidence ML): If max_prob >= 0.55
        if max_prob >= 0.55:
            results.append(
                CategorizationResult(
                    category=pred_class,
                    confidence=round(max_prob, 3),
                    source="ML_JOBLIB",
                )
            )
            continue

        # Tier 3 (Low-Confidence Regex Fallback): If max_prob < 0.55
        fallback_cat = classify_canonical_regex(raw_desc or "") or classify_canonical_regex(clean_desc or "")
        if fallback_cat:
            results.append(
                CategorizationResult(
                    category=fallback_cat,
                    confidence=round(max_prob, 3),
                    source="REGEX_FALLBACK",
                )
            )
        else:
            results.append(
                CategorizationResult(
                    category="Other",
                    confidence=round(max_prob, 3),
                    source="REGEX_FALLBACK",
                )
            )

    return results


# Pre-compiled regex patterns for deterministic category tagging
CATEGORY_RULES: List[Tuple[str, re.Pattern]] = [
    (
        "Food & Dining",
        re.compile(
            r"\b(starbucks|mcdonald|chipotle|wendy|dunkin|subway|taco\s*bell|panera|"
            r"restaurant|cafe|coffee|bistro|diner|eatery|pizza|burger|sushi|bakery|"
            r"bar|pub|grill|brew|uber\s*eats|doordash|grubhub|postmates|caviar|dining)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Groceries",
        re.compile(
            r"\b(whole\s*foods|trader\s*joe|safeway|kroger|walmart|target|costco|aldi|"
            r"heb|wegmans|publix|grocer|supermarket|market|sprouts|fresh\s*market)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Utilities",
        re.compile(
            r"\b(electric|water|gas|pge|coned|comed|internet|comcast|xfinity|verizon|"
            r"at&t|att|t-mobile|spectrum|utility|power|energy|sewer|trash|phone|broadband)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Travel",
        re.compile(
            r"\b(uber|lyft|flight|airline|delta|united|american\s*air|southwest|jetblue|"
            r"hotel|marriott|hilton|airbnb|vrbo|expedia|booking\.com|transit|train|amtrak|"
            r"metro|toll|parking|gas\s*station|shell|chevron|bp|exxon|mobil|speedway|tfl|transport|underground|rail)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Subscriptions",
        re.compile(
            r"\b(netflix|spotify|apple|google\s*storage|google\s*one|amazon\s*prime|"
            r"hulu|disney|hbo|max|nytimes|wsj|patreon|substack|github|openai|chatgpt|"
            r"midjourney|software|subscr|adobe|dropbox)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Transfers",
        re.compile(
            r"\b(transfer|zelle|venmo|wire|ach|paypal|cash\s*app|payout|internal\s*xfer|"
            r"atm\s*withdrawal|atm\s*deposit|xfer|direct\s*deposit|salary|payroll)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Shopping",
        re.compile(
            r"\b(amazon|ebay|best\s*buy|apple\s*store|ikea|home\s*depot|lowes|zara|"
            r"h&m|nordstrom|macys|nike|adidas|clothing|retail|shop|store|boutique|mall)\b",
            re.IGNORECASE,
        ),
    ),
]


def classify_category(description: Any) -> str:
    """Deterministic keyword/regex classifier for financial transactions."""
    if description is None or (isinstance(description, float) and math.isnan(description)):
        return "Other"
    text = str(description).strip().lower()
    if text in ("nan", "none", "null", ""):
        return "Other"
    for category, pattern in CATEGORY_RULES:
        if pattern.search(text):
            return category
    return "Other"


def parse_date(date_str: str, dayfirst: Optional[bool] = None, default_year: Optional[int] = None) -> Optional[date]:
    """Parse various bank date formats into a datetime.date with strict validation."""
    if not date_str or not str(date_str).strip():
        return None
    raw = str(date_str).strip()

    # Reject non-dates (headers, summaries, page numbers, accounts, amounts)
    if re.search(r"\b(page|account|balance|total|subtotal|summary|statement|usd|eur|inr|gbp|available|closing|opening|amount|debit|credit|withdrawal|deposit)\b", raw, re.IGNORECASE):
        return None
    if not re.search(r"\d", raw):
        return None

    # If cell contains multiple lines, look for the line that contains a date
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    if len(lines) > 1:
        for ln in lines:
            if re.search(r"\d", ln) and not re.search(r"\b(page|account|balance|total|summary|amount)\b", ln, re.IGNORECASE):
                d = parse_date(ln, dayfirst=dayfirst, default_year=default_year)
                if d:
                    return d

    # Normalize multilingual month names & strip weekday prefix
    norm_raw = normalize_multilingual_date_string(raw)
    had_trailing_dot = norm_raw.rstrip().endswith(".")

    # Clean characters around date
    cleaned = re.sub(r"^[^0-9a-zA-Z]+|[^0-9a-zA-Z]+$", "", norm_raw)

    # Support space-separated numeric dates: e.g. "15 01 2024" or "15 01" -> "15/01/2024"
    m_space = re.match(r"^(\d{1,2})\s+(\d{1,2})(?:\s+(\d{2,4}))?$", cleaned)
    if m_space:
        cleaned = f"{m_space.group(1)}/{m_space.group(2)}" + (f"/{m_space.group(3)}" if m_space.group(3) else "")

    # Guard: Pure time strings (e.g. 04:26 pm, 10:00 am, 16:26:00, 12:30) must be rejected
    if re.match(r"^\d{1,2}:\d{2}(?::\d{2})?(?:\.\d+)?\s*(?:am|pm)?$", cleaned, re.IGNORECASE):
        return None

    # Guard: Floats or amounts with a single dot (e.g. 5.50, 42.00) are amounts, never dates
    if re.match(r"^[+-]?\d+\.\d+$", cleaned):
        if not had_trailing_dot:
            return None

    # Guard: Pure numbers must be 6 or 8 digits to be dates (e.g. 20240101)
    if re.match(r"^\d+$", cleaned) and len(cleaned) not in (6, 8):
        return None

    # Guard: If dot is used as a date separator, it must occur at least twice (DD.MM.YYYY) or have trailing dot
    if "." in cleaned and "/" not in cleaned and "-" not in cleaned and not re.search(r"[a-zA-Z]", cleaned):
        if cleaned.count(".") < 2 and not had_trailing_dot:
            return None

    # Must contain date separators or alphabetic month characters
    if not (re.search(r"[-/]", cleaned) or "." in cleaned or re.search(r"[a-zA-Z]", cleaned)):
        return None

    # Determine dayfirst candidate order
    dayfirst_candidates: List[bool]
    if dayfirst is not None:
        dayfirst_candidates = [dayfirst, not dayfirst]
    else:
        m_num = re.match(r"^(\d{1,2})[-/\.](\d{1,2})(?:[-/\.](\d{2,4}))?", cleaned)
        if m_num:
            p1, p2 = int(m_num.group(1)), int(m_num.group(2))
            if p1 > 12 >= p2:
                dayfirst_candidates = [True, False]
            elif p2 > 12 >= p1:
                dayfirst_candidates = [False, True]
            else:
                dayfirst_candidates = [False, True]
        else:
            dayfirst_candidates = [False, True]

    sentinel = datetime(1000, 1, 1)

    # 1. Try strict parsing first (handles ISO, US, UK, German dot notation, named months)
    for df in dayfirst_candidates:
        try:
            dt = date_parser.parse(cleaned, default=sentinel, dayfirst=df, fuzzy=False)
            if dt.year == 1000 and dt.month == 1 and dt.day == 1 and (dt.hour != 0 or dt.minute != 0):
                continue
            if dt.year == 1000:
                yr = default_year or date.today().year
                return date(yr, dt.month, dt.day)
            elif 1970 <= dt.year <= 2050:
                return dt.date()
        except Exception:
            pass

    # 2. Only attempt fuzzy parse if the string matches recognized date token structures with valid month names
    MONTH_NAMES = (
        r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    )
    date_pattern = re.compile(
        r"^(?:\d{4}[-/\.]\d{1,2}[-/\.]\d{1,2}|\d{1,2}[-/\.]\d{1,2}(?:[-/\.]\d{2,4})?|"
        r"" + MONTH_NAMES + r"\s+\d{1,2},?(?:\s+\d{2,4})?|\d{1,2}\s+" + MONTH_NAMES + r"(?:\s+\d{2,4})?|"
        r"\d{1,2}[-/\.]" + MONTH_NAMES + r"(?:[-/\.]\d{2,4})?)",
        re.IGNORECASE,
    )
    if date_pattern.search(cleaned):
        for df in dayfirst_candidates:
            try:
                dt = date_parser.parse(cleaned, default=sentinel, dayfirst=df, fuzzy=True)
                if dt.year == 1000 and dt.month == 1 and dt.day == 1 and (dt.hour != 0 or dt.minute != 0):
                    continue
                if dt.year == 1000:
                    yr = default_year or date.today().year
                    return date(yr, dt.month, dt.day)
                elif 1970 <= dt.year <= 2050:
                    return dt.date()
            except Exception:
                pass

    return None


def parse_amount(amount_str: str) -> Optional[Tuple[Decimal, Optional[str]]]:
    """
    Parse an amount string.
    Returns (abs_amount, txn_type_hint) or None if unparseable.
    txn_type_hint can be 'DEBIT', 'CREDIT', or None.
    Handles US, UK, Indian, European, and Swiss currency notation,
    parentheses, trailing minus/plus signs (100.00-), and international currencies.
    """
    if not amount_str or not str(amount_str).strip():
        return None
    raw = str(amount_str).strip()

    hint = None
    if re.search(r"\b(DR|DEBIT|W/D|WITHDRAWAL|WDL)\b", raw, re.IGNORECASE):
        hint = "DEBIT"
    elif re.search(r"\b(CR|CREDIT|DEP|DEPOSIT)\b", raw, re.IGNORECASE):
        hint = "CREDIT"
    elif re.search(r"\b(Cr\.|Dr\.)\b", raw, re.IGNORECASE):
        hint = "CREDIT" if "Cr" in raw else "DEBIT"

    # Explicit plus indicates CREDIT
    has_plus = bool(re.search(r"^\s*\+", raw) or re.search(r"\+\s*(?:Rs\.?|INR|₹|\$|€|£)?\s*\d", raw) or re.search(r"\+\s*$", raw))

    cleaned = raw.strip()

    # Check for parenthesis notation for negative, e.g. ($5.75) or (120.00)
    is_paren_negative = False
    if cleaned.startswith("(") and cleaned.endswith(")"):
        is_paren_negative = True
        cleaned = cleaned[1:-1].strip()

    CURR_PAT = r"(?:Rs\.?|INR|USD|EUR|GBP|CAD|AUD|NZD|CHF|SGD|HKD|JPY|SEK|NOK|DKK|PLN|ZAR|BRL|MXN|₹|\$|€|£|¥|kr)"

    # Strip currency signs
    cleaned = re.sub(r"^[+-]?" + CURR_PAT + r"\s*", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\s*" + CURR_PAT + r"\s*$", "", cleaned, flags=re.IGNORECASE).strip()

    if cleaned.startswith("(") and cleaned.endswith(")"):
        is_paren_negative = True
        cleaned = cleaned[1:-1].strip()

    cleaned = re.sub(r"^[+-]?" + CURR_PAT + r"\s*", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\s*" + CURR_PAT + r"\s*$", "", cleaned, flags=re.IGNORECASE).strip()

    # Strip trailing/leading hint tokens
    cleaned = re.sub(r"\s*\b(DR|DEBIT|W/D|WITHDRAWAL|WDL|CR|CREDIT|DEP|DEPOSIT|Cr\.|Dr\.)\b\s*$", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"^\s*\b(DR|DEBIT|W/D|WITHDRAWAL|WDL|CR|CREDIT|DEP|DEPOSIT|Cr\.|Dr\.)\b\s*", "", cleaned, flags=re.IGNORECASE).strip()

    # Trailing minus or plus (standard accounting/SAP format: 100.00- or 100.00+)
    if re.search(r"[-–—]\s*$", cleaned):
        is_paren_negative = True
        cleaned = re.sub(r"[-–—]\s*$", "", cleaned).strip()
    if re.search(r"\+\s*$", cleaned):
        has_plus = True
        cleaned = re.sub(r"\+\s*$", "", cleaned).strip()

    if re.search(r"^\s*[-–—]", cleaned):
        is_paren_negative = True
        cleaned = re.sub(r"^\s*[-–—]", "", cleaned).strip()
    if re.search(r"^\s*\+", cleaned):
        has_plus = True
        cleaned = re.sub(r"^\s*\+", "", cleaned).strip()

    # Strip Swiss / German apostrophes (e.g. 1'250.50 or 1’250.50)
    cleaned = re.sub(r"(?<=\d)['’](?=\d)", "", cleaned)

    # Strip internal spaces used as thousand separators (e.g. 1 250,50)
    cleaned = re.sub(r"(?<=\d)[\s\u00A0]+(?=\d)", "", cleaned)

    # Guard: The core string MUST contain only digits, comma, dot, and plus/minus
    if not re.match(r"^[+-]?[\d,\.]+$", cleaned):
        return None

    # Distinguish US/Indian (1,250.50) vs European (1.250,50) decimal notations
    if "." in cleaned and "," in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned and "." not in cleaned:
        parts = cleaned.split(",")
        if len(parts) == 2 and len(re.sub(r"[^\d]", "", parts[1])) in (1, 2):
            cleaned = cleaned.replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "." in cleaned and "," not in cleaned:
        # If there are multiple dots (e.g. 1.250.000), they are European thousand separators
        if cleaned.count(".") > 1:
            cleaned = cleaned.replace(".", "")

    cleaned = re.sub(r"[^\d\.\-\+]", "", cleaned)
    if not cleaned or cleaned in ("-", "+", "."):
        return None

    # Guard against phone/account/cheque numbers (e.g. > 11 digits with no decimal)
    if "." not in cleaned and len(cleaned) > 11:
        return None

    try:
        val = Decimal(cleaned)
        if is_paren_negative or val < 0:
            val = abs(val)
            if hint is None:
                hint = "DEBIT"
        elif has_plus and hint is None:
            hint = "CREDIT"
        return (val, hint)
    except InvalidOperation:
        return None


def compute_row_hash(txn_date: date, description: str, amount: Decimal, balance: Optional[Decimal]) -> str:
    """Compute deterministic SHA-256 hash for row deduplication."""
    norm_desc = re.sub(r"\s+", " ", description.strip().lower())
    norm_amount = f"{float(amount):.2f}"
    norm_balance = f"{float(balance):.2f}" if balance is not None else ""
    raw = f"{txn_date.isoformat()}|{norm_desc}|{norm_amount}|{norm_balance}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class TableColumnMapping:
    def __init__(
        self,
        date_idx: Optional[int] = None,
        desc_idx: Optional[int] = None,
        amount_idx: Optional[int] = None,
        debit_idx: Optional[int] = None,
        credit_idx: Optional[int] = None,
        balance_idx: Optional[int] = None,
        type_idx: Optional[int] = None,
        category_idx: Optional[int] = None,
        ref_idx: Optional[int] = None,
    ):
        self.date_idx = date_idx
        self.desc_idx = desc_idx
        self.amount_idx = amount_idx
        self.debit_idx = debit_idx
        self.credit_idx = credit_idx
        self.balance_idx = balance_idx
        self.type_idx = type_idx
        self.category_idx = category_idx
        self.ref_idx = ref_idx

    @property
    def is_valid(self) -> bool:
        has_date = self.date_idx is not None
        has_desc = self.desc_idx is not None
        has_amt = self.amount_idx is not None or (self.debit_idx is not None or self.credit_idx is not None)
        return has_date and has_desc and has_amt


def detect_column_headers(header_cells: List[str]) -> TableColumnMapping:
    """Match table headers against common bank statement column names."""
    mapping = TableColumnMapping()
    primary_date_idx: Optional[int] = None
    secondary_date_idx: Optional[int] = None

    for idx, cell in enumerate(header_cells):
        norm_cell = unicodedata.normalize('NFKD', str(cell)).encode('ASCII', 'ignore').decode('utf-8')
        text = re.sub(r"[^a-zA-Z0-9/ ]", "", norm_cell.strip().lower())
        tokens = text.split()

        # Cheque / Ref number header
        if any(w in text for w in ["chq", "cheque", "ref no", "reference", "utr", "txn id", "chqno", "check no"]):
            if mapping.ref_idx is None:
                mapping.ref_idx = idx
            continue

        # Category header heuristics (check before description or spend)
        if "category" in text or "classification" in text:
            if mapping.category_idx is None:
                mapping.category_idx = idx
            continue

        # Date header heuristics: distinguish primary transaction date from secondary value date
        if any(w in text for w in ["value date", "val date", "val dt", "value dt", "valuta", "wertstellung", "fecha valor", "data valuta", "data valor", "valutadatum"]):
            if secondary_date_idx is None:
                secondary_date_idx = idx
        elif any(w in tokens for w in ["date", "postdate", "transdate", "txndate", "trandate", "postingdate", "buchungstag", "belegdatum", "fecha", "buchung", "datum", "data"]) or any(k in text for k in ("date", "fecha", "datum", "data operazione", "data operacji", "data ksiegowania", "data contabile", "transactiedatum", "boekingsdatum")):
            if primary_date_idx is None:
                primary_date_idx = idx

        # Description header heuristics
        elif any(w in text for w in ["description", "particular", "narration", "details", "narrative", "payee", "memo", "remarks", "payment details", "merchant", "verwendungszweck", "buchungstext", "vorgang", "empfaenger", "beguenstigter", "libelle", "operation", "concepto", "movimiento", "omschrijving", "mededelingen", "betalingskenmerk", "descrizione", "causale", "dettagli", "historico", "descricao", "lancamento", "opis", "tytul"]):
            if mapping.desc_idx is None:
                mapping.desc_idx = idx

        # Combined Debit / Credit header heuristics (e.g. "Debit / Credit", "Withdrawal / Deposit", "Paid Out / In", "Money Out / In", "Dr / Cr")
        elif (
            ("debit" in text and "credit" in text)
            or ("withdrawal" in text and "deposit" in text)
            or ("paid out" in text and "paid in" in text)
            or ("money out" in text and "money in" in text)
            or ("soll" in text and "haben" in text)
            or ("af" in tokens and "bij" in tokens)
            or ("dare" in tokens and "avere" in tokens)
            or ("dr" in tokens and "cr" in tokens)
        ):
            if mapping.amount_idx is None:
                mapping.amount_idx = idx

        # Debit header heuristics
        elif any(w in text for w in ["debit", "withdrawal", "withdrawals", "paid out", "money out", "spend", "charge", "debits", "payments", "dr amt", "soll", "ausgaben", "belastung", "lastschrift", "cargo", "adeudo", "cargos", "gastos", "retraits", "retrait", "depenses", "af", "afschrijving", "addebiti", "uscite", "dare", "debito", "saida", "obciazenia", "wyplaty"]) or text in ("out", "dr", "af"):
            if mapping.debit_idx is None:
                mapping.debit_idx = idx

        # Credit header heuristics
        elif any(w in text for w in ["credit", "deposit", "deposits", "paid in", "money in", "lodgement", "credits", "receipts", "cr amt", "haben", "einnahmen", "gutschrift", "abono", "abonos", "ingreso", "ingresos", "depots", "versements", "bij", "bijschrijving", "accrediti", "entrate", "avere", "credito", "entrada", "uznania", "wplaty"]) or text in ("in", "cr", "bij"):
            if mapping.credit_idx is None:
                mapping.credit_idx = idx

        # Balance header heuristics
        elif any(w in text for w in ["balance", "closing", "running", "available", "ledger bal", "bal", "saldo", "kontostand", "solde", "schlusssaldo"]):
            if mapping.balance_idx is None:
                mapping.balance_idx = idx

        # General Amount header heuristics
        elif any(w in text for w in ["amount", "total", "net", "betrag", "montant", "importe", "monto", "bedrag", "importo", "valor", "kwota", "wartosc"]):
            if mapping.amount_idx is None:
                mapping.amount_idx = idx

        # Txn Type header heuristics
        elif any(w in text for w in ["type", "d/c", "dr/cr", "cr/dr", "indicator", "sign"]) or text in ("dr", "cr"):
            if mapping.type_idx is None:
                mapping.type_idx = idx

    mapping.date_idx = primary_date_idx if primary_date_idx is not None else secondary_date_idx
    return mapping


def infer_columns_statistically(rows: List[List[str]]) -> TableColumnMapping:
    """Infer column mapping by statistical inspection of row cell data, properly distinguishing dates, cheque numbers, and monetary amounts."""
    if not rows:
        return TableColumnMapping()

    sample_rows = [r for r in rows[:30] if r and any(str(c).strip() for c in r)]
    if not sample_rows:
        return TableColumnMapping()

    max_cols = max(len(r) for r in sample_rows)
    date_scores = [0] * max_cols
    amount_scores = [0] * max_cols
    decimal_scores = [0] * max_cols
    leading_zero_scores = [0] * max_cols
    text_lengths = [0] * max_cols
    row_count = len(sample_rows)

    for r in sample_rows:
        for idx in range(min(len(r), max_cols)):
            cell_str = str(r[idx]).strip()
            if not cell_str:
                continue
            if parse_date(cell_str) is not None:
                date_scores[idx] += 1
            p_amt = parse_amount(cell_str)
            if p_amt is not None:
                amount_scores[idx] += 1
                if "." in cell_str or "," in cell_str or any(curr in cell_str for curr in ("$", "₹", "€", "£")):
                    decimal_scores[idx] += 1
                if re.match(r"^0\d+", cell_str):
                    leading_zero_scores[idx] += 1
            text_lengths[idx] += len(cell_str)

    # Date columns (can have primary date and secondary value date)
    date_cols = [idx for idx, sc in enumerate(date_scores) if sc >= max(1, row_count // 3)]
    best_date_idx = date_cols[0] if date_cols else None

    # Ref / Cheque column identification:
    # A column where cells have leading zeros or pure integers while other amount columns have decimals
    ref_col_idx = None
    for idx in range(max_cols):
        if idx in date_cols:
            continue
        if leading_zero_scores[idx] >= 1 or (amount_scores[idx] >= 1 and decimal_scores[idx] == 0 and any(decimal_scores)):
            ref_col_idx = idx
            break

    # Description column: longest text length, excluding date, ref, and decimal amount cols
    best_desc_idx = None
    max_len = -1
    for idx in range(max_cols):
        if idx in date_cols or idx == ref_col_idx:
            continue
        if decimal_scores[idx] >= 2 and decimal_scores[idx] >= amount_scores[idx] // 2:
            continue
        if text_lengths[idx] > max_len:
            max_len = text_lengths[idx]
            best_desc_idx = idx

    # Monetary amount columns: amount_scores >= 1, not date, not desc, not ref
    candidate_amt_cols = [
        idx for idx, sc in enumerate(amount_scores)
        if sc >= 1 and idx not in date_cols and idx != best_desc_idx and idx != ref_col_idx
    ]

    mapping = TableColumnMapping(date_idx=best_date_idx, desc_idx=best_desc_idx, ref_idx=ref_col_idx)

    if len(candidate_amt_cols) == 1:
        mapping.amount_idx = candidate_amt_cols[0]
    elif len(candidate_amt_cols) == 2:
        mapping.amount_idx = candidate_amt_cols[0]
        mapping.balance_idx = candidate_amt_cols[1]
    elif len(candidate_amt_cols) >= 3:
        mapping.debit_idx = candidate_amt_cols[0]
        mapping.credit_idx = candidate_amt_cols[1]
        mapping.balance_idx = candidate_amt_cols[-1]

    # Standard fallback patterns if columns still unassigned:
    # 7 cols: [date, desc, ref, val_date, debit, credit, bal]
    if max_cols >= 7 and best_date_idx == 0 and best_desc_idx == 1 and (mapping.debit_idx is None or mapping.credit_idx is None):
        mapping.ref_idx = 2
        mapping.debit_idx = 4
        mapping.credit_idx = 5
        mapping.balance_idx = 6
    # 6 cols: [date, desc, ref, debit, credit, bal]
    elif max_cols == 6 and best_date_idx == 0 and best_desc_idx == 1 and (mapping.debit_idx is None or mapping.credit_idx is None):
        mapping.ref_idx = 2
        mapping.debit_idx = 3
        mapping.credit_idx = 4
        mapping.balance_idx = 5
    # 5 cols: [date, desc, debit, credit, bal]
    elif max_cols == 5 and best_date_idx == 0 and best_desc_idx == 1 and (mapping.debit_idx is None or mapping.credit_idx is None):
        mapping.debit_idx = 2
        mapping.credit_idx = 3
        mapping.balance_idx = 4

    return mapping


def normalize_table_rows(
    rows: List[List[str]],
    use_ml: bool = False,
    inherited_mapping: Optional[TableColumnMapping] = None,
    initial_balance: Optional[Decimal] = None,
    return_state: bool = False,
) -> Any:
    """
    Given a 2D grid of text strings representing a table from a bank statement,
    locate headers, map columns, parse rows, tag categories, and build canonical TransactionCreate DTOs.
    """
    if not rows or len(rows) < 2:
        if return_state:
            return [], inherited_mapping or TableColumnMapping(), initial_balance
        return []

    # 1. Locate header row: inspect up to 25 rows, and also test 2-row merged headers
    header_idx = -1
    mapping = TableColumnMapping()
    search_limit = min(25, len(rows))

    for i in range(search_limit):
        m = detect_column_headers(rows[i])
        if m.is_valid:
            mapping = m
            header_idx = i
            break
        # Test 2-row merged header with rows[i+1]
        if i + 1 < len(rows):
            merged = [
                f"{rows[i][k] if k < len(rows[i]) else ''} {rows[i+1][k] if k < len(rows[i+1]) else ''}".strip()
                for k in range(max(len(rows[i]), len(rows[i+1])))
            ]
            m_merged = detect_column_headers(merged)
            if m_merged.is_valid:
                mapping = m_merged
                header_idx = i + 1
                break

    # If no valid header found in this table, check if inherited_mapping can be used
    if (not mapping.is_valid or header_idx == -1) and inherited_mapping is not None and inherited_mapping.is_valid:
        mapping = inherited_mapping
        if mapping.date_idx is not None and mapping.date_idx < len(rows[0]) and parse_date(rows[0][mapping.date_idx]) is not None:
            header_idx = -1
        else:
            header_idx = 0

    # If still not valid, try statistical inference
    if not mapping.is_valid or header_idx == -1:
        stat_map = infer_columns_statistically(rows)
        if stat_map.is_valid:
            mapping = stat_map
            # If row 0 contains a valid date, then all rows are data rows (header_idx = -1)
            if mapping.date_idx is not None and mapping.date_idx < len(rows[0]) and parse_date(rows[0][mapping.date_idx]) is not None:
                header_idx = -1
            else:
                header_idx = 0
        else:
            num_cols = len(rows[0])
            if num_cols >= 3:
                mapping = TableColumnMapping(
                    date_idx=0,
                    desc_idx=1,
                    amount_idx=2 if num_cols == 3 else None,
                    debit_idx=2 if num_cols >= 4 else None,
                    credit_idx=3 if num_cols >= 4 else None,
                    balance_idx=4 if num_cols >= 5 else None,
                )
                header_idx = 0
            else:
                if return_state:
                    return [], mapping, initial_balance
                return []

    # 2. Pre-scan table dates to infer global dayfirst and document year
    table_dayfirst: Optional[bool] = None
    all_date_tuples: List[Tuple[int, int]] = []
    full_table_text = " ".join(" ".join(str(c) for c in r) for r in rows[:15]).lower()

    table_year = None
    for row in rows[header_idx + 1:header_idx + 25]:
        if mapping.date_idx is not None and mapping.date_idx < len(row):
            parsed_test = parse_date(row[mapping.date_idx])
            if parsed_test and 1990 <= parsed_test.year <= date.today().year + 1:
                table_year = parsed_test.year
                break

    if table_year is None:
        m_yr = re.search(r"(?<![\$\€\£\¥\₹\d\.,])(19\d\d|20[0-3]\d)(?!\.\d)", full_table_text)
        if m_yr:
            table_year = int(m_yr.group(1))

    # Detect Indian, UK, European or Commonwealth bank markers (standard dayfirst=True: DD/MM/YYYY)
    is_dayfirst_region = False
    if any(sym in full_table_text for sym in ("₹", "£", "€", "¥")):
        is_dayfirst_region = True
    elif re.search(
        r"\b(inr|rs|neft|rtgs|imps|upi|ifsc|gbp|sort\s*code|iban|bic|bsb|aud|nzd|sgd|chf|eur|euro|débit|crédit|solde|virement|libellé|buchung|buchungstag|soll|haben|saldo|valuta|wertstellung|cargo|abono|fecha|datum|omschrijving|af|bij)\b",
        full_table_text,
        re.IGNORECASE,
    ):
        is_dayfirst_region = True

    for row in rows[header_idx + 1:]:
        if mapping.date_idx is not None and mapping.date_idx < len(row):
            m = re.match(r"^\s*(\d{1,2})[-/\.](\d{1,2})(?:[-/\.]\d{2,4})?", str(row[mapping.date_idx]).strip())
            if m:
                n1, n2 = int(m.group(1)), int(m.group(2))
                if 1 <= n1 <= 31 and 1 <= n2 <= 31 and (n1 <= 12 or n2 <= 12):
                    all_date_tuples.append((n1, n2))

    if any(t[0] > 12 for t in all_date_tuples):
        table_dayfirst = True
    elif any(t[1] > 12 for t in all_date_tuples):
        table_dayfirst = False
    elif len(all_date_tuples) >= 2:
        p1_vals = [t[0] for t in all_date_tuples]
        p2_vals = [t[1] for t in all_date_tuples]
        if len(set(p2_vals)) == 1 and len(set(p1_vals)) > 1:
            table_dayfirst = True
        elif len(set(p1_vals)) == 1 and len(set(p2_vals)) > 1:
            table_dayfirst = False
        elif is_dayfirst_region:
            table_dayfirst = True
    elif is_dayfirst_region:
        table_dayfirst = True

    # 3. Parse data rows with multi-line description merging and section type tracking
    parsed_rows: List[Dict[str, Any]] = []
    current_section_type: Optional[str] = None
    last_balance: Optional[Decimal] = initial_balance

    SUMMARY_IGNORE = re.compile(
        r"\b(opening balance|closing balance|carried forward|brought forward|b/f|c/f|"
        r"transaction total|total debit|total credit|page \d+|"
        r"anfangssaldo|endsaldo|zwischensumme|gesamtsumme|übertrag|uebertrag|"
        r"ancien solde|nouveau solde|total des débits|total des credits|solde initial|solde final|"
        r"saldo anterior|saldo inicial|saldo final|total cargos|total abonos|"
        r"saldo iniziale|saldo finale|totale entrate|totale uscite|vorig saldo|nieuw saldo)\b",
        re.IGNORECASE,
    )

    for row in rows[header_idx + 1:]:
        if not row or all(not str(c).strip() for c in row):
            continue

        full_row_str = " ".join(str(c) for c in row).strip()

        # Track section headers (e.g. Chase / BoA statements split into Deposits vs Withdrawals)
        if re.search(r"\b(deposits?\s+and\s+(?:other\s+)?additions?|credits?)\b", full_row_str, re.IGNORECASE):
            current_section_type = "CREDIT"
        elif re.search(r"\b(withdrawals?\s+and\s+(?:other\s+)?subtractions?|debits?|checks?\s+paid)\b", full_row_str, re.IGNORECASE):
            current_section_type = "DEBIT"

        # Check for date
        parsed_d = None
        if mapping.date_idx is not None and mapping.date_idx < len(row):
            parsed_d = parse_date(row[mapping.date_idx], dayfirst=table_dayfirst, default_year=table_year)

        # If no date at date_idx, check first 3 cells in case of column shift
        if not parsed_d:
            for cell_val in row[:min(len(row), 3)]:
                parsed_d = parse_date(cell_val, dayfirst=table_dayfirst, default_year=table_year)
                if parsed_d:
                    break

        # If still no date: Check if this is a multiline continuation of previous transaction description
        if not parsed_d:
            if parsed_rows and not SUMMARY_IGNORE.search(full_row_str):
                has_amt = False
                for cell in row:
                    if parse_amount(str(cell)) is not None:
                        has_amt = True
                        break
                if not has_amt:
                    desc_extra = ""
                    if mapping.desc_idx is not None and mapping.desc_idx < len(row) and str(row[mapping.desc_idx]).strip():
                        desc_extra = str(row[mapping.desc_idx]).strip()
                    else:
                        non_empty = [str(c).strip() for c in row if str(c).strip()]
                        desc_extra = " ".join(non_empty)

                    if desc_extra:
                        parsed_rows[-1]["description"] = (parsed_rows[-1]["description"] + " " + desc_extra).strip()
            continue

        # Extract description
        desc_raw = row[mapping.desc_idx] if mapping.desc_idx is not None and mapping.desc_idx < len(row) else ""
        description = re.sub(r"\s+", " ", str(desc_raw).strip())
        if not description:
            other_text = []
            for k, c in enumerate(row):
                if k != mapping.date_idx and k not in (mapping.amount_idx, mapping.debit_idx, mapping.credit_idx, mapping.balance_idx):
                    s = str(c).strip()
                    if s and parse_amount(s) is None:
                        other_text.append(s)
            description = " ".join(other_text).strip() or "Unlabeled Transaction"

        # Extract amount and txn_type
        amount: Optional[Decimal] = None
        txn_type: str = "DEBIT"
        type_explicitly_set = False

        # Check separate debit/credit columns first
        if mapping.debit_idx is not None and mapping.debit_idx < len(row) and str(row[mapping.debit_idx]).strip():
            parsed_debit = parse_amount(str(row[mapping.debit_idx]))
            if parsed_debit and parsed_debit[0] > 0:
                amount = parsed_debit[0]
                txn_type = "DEBIT"
                type_explicitly_set = True

        if amount is None and mapping.credit_idx is not None and mapping.credit_idx < len(row) and str(row[mapping.credit_idx]).strip():
            parsed_credit = parse_amount(str(row[mapping.credit_idx]))
            if parsed_credit and parsed_credit[0] > 0:
                amount = parsed_credit[0]
                txn_type = "CREDIT"
                type_explicitly_set = True

        # If still none, check general amount column
        if amount is None and mapping.amount_idx is not None and mapping.amount_idx < len(row) and str(row[mapping.amount_idx]).strip():
            parsed_gen = parse_amount(str(row[mapping.amount_idx]))
            if parsed_gen and parsed_gen[0] > 0:
                amount = parsed_gen[0]
                if parsed_gen[1]:
                    txn_type = parsed_gen[1]
                    type_explicitly_set = True
                else:
                    if mapping.type_idx is not None and mapping.type_idx < len(row):
                        t_str = str(row[mapping.type_idx]).strip().upper()
                        if any(k in t_str for k in ("CR", "DEP", "CREDIT")) or t_str == "C":
                            txn_type = "CREDIT"
                            type_explicitly_set = True
                        elif any(k in t_str for k in ("DR", "WDL", "DEBIT")) or t_str == "D":
                            txn_type = "DEBIT"
                            type_explicitly_set = True

        if amount is None or amount == Decimal("0.00"):
            continue

        # Extract balance
        balance: Optional[Decimal] = None
        if mapping.balance_idx is not None and mapping.balance_idx < len(row) and str(row[mapping.balance_idx]).strip():
            parsed_bal = parse_amount(str(row[mapping.balance_idx]))
            if parsed_bal:
                balance = parsed_bal[0]

        # Running balance delta inference if txn_type was not explicitly set by separate column or valid type token
        if not type_explicitly_set:
            if balance is not None and last_balance is not None:
                delta = balance - last_balance
                if delta > Decimal("0.01"):
                    txn_type = "CREDIT"
                elif delta < -Decimal("0.01"):
                    txn_type = "DEBIT"
            elif current_section_type is not None:
                txn_type = current_section_type
            elif re.search(r"\b(salary|stipend|dividend|interest|refund|payroll|bonus|deposit)\b", description, re.IGNORECASE):
                txn_type = "CREDIT"

        if balance is not None:
            last_balance = balance

        raw_cat = ""
        if mapping.category_idx is not None and mapping.category_idx < len(row) and str(row[mapping.category_idx]).strip():
            raw_cat = str(row[mapping.category_idx]).strip()

        parsed_rows.append({
            "txn_date": parsed_d,
            "description": description,
            "amount": amount,
            "txn_type": txn_type,
            "balance": balance,
            "raw_category": raw_cat,
        })

    if not parsed_rows:
        return []

    transactions: List[TransactionCreate] = []

    if use_ml:
        batch_results = categorize_transactions_batch(
            [r["description"] for r in parsed_rows],
            [r["txn_type"] for r in parsed_rows],
        )
        for r, b_res in zip(parsed_rows, batch_results):
            raw_cat = r["raw_category"]
            if raw_cat:
                classified = classify_category(raw_cat)
                if classified != "Other":
                    cat = LEGACY_TO_CANONICAL.get(classified, classified)
                else:
                    cat = raw_cat
                conf = 1.0
                src = "STATEMENT_COLUMN"
            else:
                cat = b_res.category
                conf = b_res.confidence
                src = b_res.source

            row_hash = compute_row_hash(r["txn_date"], r["description"], r["amount"], r["balance"])
            transactions.append(
                TransactionCreate(
                    txn_date=r["txn_date"],
                    description=r["description"],
                    amount=r["amount"],
                    txn_type=r["txn_type"],
                    category=cat,
                    category_confidence=conf,
                    category_source=src,
                    balance=r["balance"],
                    row_hash=row_hash,
                )
            )
    else:
        for r in parsed_rows:
            category = "Other"
            raw_cat = r["raw_category"]
            if raw_cat:
                classified = classify_category(raw_cat)
                category = classified if classified != "Other" else raw_cat
            if category == "Other":
                category = classify_category(r["description"])

            row_hash = compute_row_hash(r["txn_date"], r["description"], r["amount"], r["balance"])
            transactions.append(
                TransactionCreate(
                    txn_date=r["txn_date"],
                    description=r["description"],
                    amount=r["amount"],
                    txn_type=r["txn_type"],
                    category=category,
                    category_confidence=None,
                    category_source=None,
                    balance=r["balance"],
                    row_hash=row_hash,
                )
            )

    if return_state:
        return transactions, mapping, last_balance
    return transactions
