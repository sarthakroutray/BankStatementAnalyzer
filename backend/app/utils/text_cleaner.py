import math
import re

_DATE_PATTERN = re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b")
_IFSC_PATTERN = re.compile(r"\b[a-z]{4}0[a-z0-9]{6}\b")
_REF_UTR_PATTERN = re.compile(r"\b\d{6,}\b")
_CARD_MASK_PATTERN = re.compile(r"\b\d*x{2,}\d*\b|x{2,}\d*")
_UPI_HANDLE_PATTERN = re.compile(r"@[a-z0-9]+")
_DELIMITERS_PATTERN = re.compile(r"[/\\_\-*:\.,;\(\)\[\]\|]")
_WHITESPACE_PATTERN = re.compile(r"\s+")


def clean_bank_narration(text: str) -> str:
    """
    Clean bank statement transaction narration by:
    1. Lowercasing text.
    2. Stripping dates, IFSC codes, 6+ digit reference/UTR numbers,
       masked card numbers (including bin prefixes), and UPI handles.
    3. Replacing delimiters (/\\-_*:.,;()[]) with spaces and collapsing whitespace.
    """
    if text is None:
        return ""
    if isinstance(text, float) and math.isnan(text):
        return ""
    cleaned = str(text).lower()
    if cleaned in ("nan", "none", "null", ""):
        return ""

    cleaned = _DATE_PATTERN.sub(" ", cleaned)
    cleaned = _IFSC_PATTERN.sub(" ", cleaned)
    cleaned = _CARD_MASK_PATTERN.sub(" ", cleaned)
    cleaned = _REF_UTR_PATTERN.sub(" ", cleaned)
    cleaned = _UPI_HANDLE_PATTERN.sub(" ", cleaned)
    cleaned = _DELIMITERS_PATTERN.sub(" ", cleaned)
    cleaned = _WHITESPACE_PATTERN.sub(" ", cleaned).strip()
    return cleaned
