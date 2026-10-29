import io
import json
import logging
import os
import re
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import unicodedata

import numpy as np
import opendataloader_pdf
from PIL import Image

try:
    import pdf2image
except ImportError:
    pdf2image = None

try:
    from rapidocr_onnxruntime import RapidOCR
except ImportError:
    RapidOCR = None

from app.schemas import TransactionCreate
from app.services.normalizer import (
    MULTILINGUAL_MONTH_MAP,
    categorize_transactions_batch,
    compute_row_hash,
    normalize_table_rows,
    parse_amount,
    parse_date,
)

logger = logging.getLogger("pdf_extractor")


def extract_cell_text(elem: Dict[str, Any]) -> str:
    """Extract all text contents recursively from a table cell object."""
    pieces: List[str] = []
    if "content" in elem and isinstance(elem["content"], str):
        pieces.append(elem["content"])

    for kid in elem.get("kids", []):
        if isinstance(kid, dict):
            kid_text = extract_cell_text(kid)
            if kid_text:
                pieces.append(kid_text)

    return " ".join(pieces).strip()


def parse_opendataloader_json(data: Any) -> List[List[List[str]]]:
    """
    Traverse opendataloader-pdf output and extract all table structures as 2D lists of strings.
    Returns: List of tables, where each table is a List of rows, and each row is a List of cell strings.
    """
    tables: List[List[List[str]]] = []

    def search_elements(element: Any):
        if isinstance(element, dict):
            if element.get("type") == "table":
                table_grid: List[List[str]] = []
                for row_elem in element.get("rows", []):
                    if not isinstance(row_elem, dict):
                        continue
                    row_cells: List[str] = []
                    for cell_elem in row_elem.get("cells", []):
                        if isinstance(cell_elem, dict):
                            row_cells.append(extract_cell_text(cell_elem))
                        else:
                            row_cells.append(str(cell_elem))
                    if any(c.strip() for c in row_cells):
                        table_grid.append(row_cells)
                if table_grid:
                    tables.append(table_grid)
            # Traverse children
            for child in element.get("kids", []):
                search_elements(child)
        elif isinstance(element, list):
            for item in element:
                search_elements(item)

    search_elements(data)
    return tables


def extract_tables_from_pdf(pdf_bytes: bytes, filename: str = "statement.pdf") -> List[TransactionCreate]:
    """
    Write PDF bytes to a temporary directory, run opendataloader-pdf to JSON,
    and parse extracted tables into normalized TransactionCreate DTOs.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        pdf_path = os.path.join(tmp_dir, filename)
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)

        out_dir = os.path.join(tmp_dir, "output")
        os.makedirs(out_dir, exist_ok=True)

        all_transactions: List[TransactionCreate] = []

        try:
            opendataloader_pdf.convert(
                input_path=[pdf_path],
                output_dir=out_dir,
                format="json",
                quiet=True
            )

            # Find all JSON files in output directory
            json_files = list(Path(out_dir).glob("*.json"))
            for jf in json_files:
                try:
                    with open(jf, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    extracted_tables = parse_opendataloader_json(data)
                    last_valid_mapping = None
                    last_balance = None
                    for table in extracted_tables:
                        txns, last_valid_mapping, last_balance = normalize_table_rows(
                            table,
                            use_ml=True,
                            inherited_mapping=last_valid_mapping,
                            initial_balance=last_balance,
                            return_state=True,
                        )
                        all_transactions.extend(txns)
                except Exception as ex:
                    logger.warning(f"Error parsing json file {jf}: {ex}")

        except Exception as e:
            logger.error(f"opendataloader_pdf execution failed: {e}")

        # Fallback to pypdf regex parsing if opendataloader returned 0 rows
        if not all_transactions:
            try:
                fallback_txns = extract_transactions_via_pypdf_fallback(pdf_path)
                if fallback_txns:
                    all_transactions.extend(fallback_txns)
            except Exception as e:
                logger.warning(f"pypdf fallback extraction failed: {e}")

        # Fallback to RapidOCR for scanned PDFs if still 0 rows
        if not all_transactions:
            try:
                if pdf2image is not None and RapidOCR is not None:
                    images = pdf2image.convert_from_bytes(pdf_bytes, dpi=200)
                    img_arrays = [np.array(im.convert("RGB")) for im in images]
                    ocr_txns = extract_transactions_from_images(img_arrays)
                    if ocr_txns:
                        all_transactions.extend(ocr_txns)
            except Exception as e:
                logger.warning(f"OCR fallback extraction failed: {e}")

        # Deduplicate transactions in-memory by row_hash
        seen_hashes = set()
        deduped: List[TransactionCreate] = []
        for txn in all_transactions:
            if txn.row_hash not in seen_hashes:
                seen_hashes.add(txn.row_hash)
                deduped.append(txn)

        return deduped


def extract_transactions_via_pypdf_fallback(pdf_path: str) -> List[TransactionCreate]:
    """
    Fallback parser using pypdf to extract raw text lines and tables if structured tables weren't detected.
    Handles single-column, multi-column, multiline narrations, and diverse bank layouts.
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        return []

    reader = PdfReader(pdf_path)
    all_pages_lines: List[str] = []
    for page in reader.pages:
        txt = page.extract_text() or ""
        for raw_line in txt.splitlines():
            cleaned_line = raw_line.strip()
            if cleaned_line:
                all_pages_lines.append(cleaned_line)

    if not all_pages_lines:
        return []

    MONTH_NAMES = (
        r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    )
    date_regex = re.compile(
        r"(?:\b\d{4}[-/\.]\d{1,2}[-/\.]\d{1,2}\b|"
        r"\b\d{1,2}[-/\.]\d{1,2}(?:[-/\.]\d{2,4})?\b|"
        r"\b\d{1,2}[-/\.]" + MONTH_NAMES + r"(?:[-/\.]\d{2,4})?\b|"
        r"\b\d{1,2}\s+" + MONTH_NAMES + r"(?:\s+\d{2,4})?\b|"
        r"\b" + MONTH_NAMES + r"\s+\d{1,2},?(?:\s+\d{2,4})?\b)",
        re.IGNORECASE,
    )

    CURR_SYM = r"(?:\$|€|£|¥|₹|kr|Rs\.?|INR|USD|EUR|GBP|CAD|AUD|NZD|CHF|SGD|HKD|JPY|PLN|SEK|NOK|DKK|ZAR|BRL)"
    amount_regex = re.compile(
        r"(?:(?<=\s)|^)[+-]?" + CURR_SYM + r"?\s*\(?[\d]+(?:[,\. '’\u00A0]\d{3})*(?:[\.,]\d{1,2})?\)?\s*" + CURR_SYM + r"?(?:\s*[-+])?(?:\s*(?:CR|DR|Cr|Dr))?(?=\s|$)",
        re.IGNORECASE,
    )

    summary_pattern = re.compile(
        r"\b(opening balance|closing balance|carried forward|brought forward|b/f|c/f|"
        r"total debit|total credit|page \d+|account summary|"
        r"anfangssaldo|endsaldo|zwischensumme|gesamtsumme|übertrag|uebertrag|"
        r"ancien solde|nouveau solde|total des débits|total des credits|solde initial|solde final|"
        r"saldo anterior|saldo inicial|saldo final|total cargos|total abonos|"
        r"saldo iniziale|saldo finale|totale entrate|totale uscite|vorig saldo|nieuw saldo)\b",
        re.IGNORECASE,
    )

    same_line_count = 0
    for line in all_pages_lines:
        if summary_pattern.search(line):
            continue
        if re.search(r"[-–to]+\s*(?:" + MONTH_NAMES + r"\s+\d{1,2}|\d{1,2}\s+" + MONTH_NAMES + r"|\d{1,2}[-/\.]\d{1,2})", line, re.IGNORECASE):
            continue
        d_m = date_regex.search(line)
        if d_m:
            post = line[d_m.end():]
            for a_m in amount_regex.finditer(post):
                amt_tok = a_m.group(0).strip()
                if re.match(r"^(19\d\d|20\d\d)$", amt_tok):
                    continue
                same_line_count += 1
                break

    has_same_line_records = (same_line_count >= 2)

    reconstructed_rows: List[List[str]] = []
    reconstructed_rows.append(["Date", "Description", "Amount", "Type", "Balance"])

    if has_same_line_records:
        for line in all_pages_lines:
            if summary_pattern.search(line):
                continue

            d_match = date_regex.search(line)
            if not d_match:
                if len(reconstructed_rows) > 1 and not amount_regex.search(line):
                    if not any(k in line.upper() for k in ("DATE", "PARTICULAR", "DEBIT", "CREDIT", "BALANCE")):
                        reconstructed_rows[-1][1] = (reconstructed_rows[-1][1] + " " + line).strip()
                continue

            dt_str = d_match.group(0)
            post_date_text = line[d_match.end():]

            amt_matches = list(amount_regex.finditer(post_date_text))
            if not amt_matches:
                continue

            first_amt_start = amt_matches[0].start()
            desc = post_date_text[:first_amt_start].strip()
            desc = re.sub(r"^[-/:\s]+|[-/:\s]+$", "", desc).strip() or "Unlabeled Transaction"

            amts = [m.group(0).strip() for m in amt_matches]
            amt_str = ""
            bal_str = ""
            type_str = ""

            if len(amts) == 1:
                amt_str = amts[0]
            elif len(amts) == 2:
                amt_str = amts[0]
                bal_str = amts[1]
            elif len(amts) >= 3:
                bal_str = amts[-1]
                p0 = parse_amount(amts[0])
                p1 = parse_amount(amts[1])
                val0 = p0[0] if p0 else Decimal("0")
                val1 = p1[0] if p1 else Decimal("0")
                if val0 > 0 and val1 == 0:
                    amt_str = str(val0)
                    type_str = "DEBIT"
                elif val1 > 0 and val0 == 0:
                    amt_str = str(val1)
                    type_str = "CREDIT"
                elif val0 > 0:
                    amt_str = str(val0)
                    type_str = "DEBIT"
                else:
                    amt_str = amts[0]

            if not type_str:
                p_cur = parse_amount(amt_str)
                if p_cur and p_cur[1]:
                    type_str = p_cur[1]
                elif re.search(r"\b(CR|CREDIT|DEP)\b", line, re.IGNORECASE):
                    type_str = "CREDIT"
                elif re.search(r"\b(DR|DEBIT|WDL)\b", line, re.IGNORECASE):
                    type_str = "DEBIT"

            reconstructed_rows.append([dt_str, desc, amt_str, type_str, bal_str])
    else:
        current_record: Optional[Dict[str, Any]] = None
        for line in all_pages_lines:
            if summary_pattern.search(line):
                continue

            # Header line check: skip only exact column headers
            if line.upper() in ("DATE", "TRANSACTION DETAILS", "TYPE", "AMOUNT", "BALANCE", "NARRATION", "PARTICULARS", "VALUE DATE", "STATEMENT", "ACCOUNT SUMMARY"):
                continue

            # Pure time string check (e.g. 04:26 pm, 10:00 am)
            if re.match(r"^\d{1,2}:\d{2}(?::\d{2})?(?:\.\d+)?\s*(?:am|pm)?$", line, re.IGNORECASE):
                continue

            # Check if this line is a txn type token
            if line.upper() in ("DEBIT", "CREDIT", "DR", "CR", "DR.", "CR.", "DEP", "WDL"):
                if current_record is not None:
                    current_record["type"] = "CREDIT" if any(k in line.upper() for k in ("CR", "DEP", "CREDIT")) else "DEBIT"
                continue

            d_val = parse_date(line)
            if d_val is not None:
                if current_record and current_record["amts"]:
                    amts = current_record["amts"]
                    desc = " ".join(current_record["desc"]).strip() or "Unlabeled Transaction"
                    amt_str, bal_str = "", ""
                    type_str = current_record.get("type", "")
                    if len(amts) == 1:
                        amt_str = amts[0]
                    elif len(amts) == 2:
                        amt_str = amts[0]
                        bal_str = amts[1]
                    elif len(amts) >= 3:
                        bal_str = amts[-1]
                        p0 = parse_amount(amts[0])
                        p1 = parse_amount(amts[1])
                        val0 = p0[0] if p0 else Decimal("0")
                        val1 = p1[0] if p1 else Decimal("0")
                        if val0 > 0 and val1 == 0:
                            amt_str = str(val0)
                            type_str = "DEBIT"
                        elif val1 > 0 and val0 == 0:
                            amt_str = str(val1)
                            type_str = "CREDIT"
                        elif val0 > 0:
                            amt_str = str(val0)
                            type_str = "DEBIT"
                        else:
                            amt_str = amts[0]

                    if not type_str:
                        p_cur = parse_amount(amt_str)
                        if p_cur and p_cur[1]:
                            type_str = p_cur[1]

                    reconstructed_rows.append([current_record["date"], desc, amt_str, type_str, bal_str])
                current_record = {"date": line, "desc": [], "amts": [], "type": ""}
            elif current_record is not None:
                p_amt = parse_amount(line)
                if p_amt is not None:
                    current_record["amts"].append(line)
                    if p_amt[1] and not current_record.get("type"):
                        current_record["type"] = p_amt[1]
                else:
                    current_record["desc"].append(line)

        if current_record and current_record["amts"]:
            amts = current_record["amts"]
            desc = " ".join(current_record["desc"]).strip() or "Unlabeled Transaction"
            amt_str, bal_str = "", ""
            type_str = current_record.get("type", "")
            if len(amts) == 1:
                amt_str = amts[0]
            elif len(amts) == 2:
                amt_str = amts[0]
                bal_str = amts[1]
            elif len(amts) >= 3:
                bal_str = amts[-1]
                p0 = parse_amount(amts[0])
                p1 = parse_amount(amts[1])
                val0 = p0[0] if p0 else Decimal("0")
                val1 = p1[0] if p1 else Decimal("0")
                if val0 > 0 and val1 == 0:
                    amt_str = str(val0)
                    type_str = "DEBIT"
                elif val1 > 0 and val0 == 0:
                    amt_str = str(val1)
                    type_str = "CREDIT"
                elif val0 > 0:
                    amt_str = str(val0)
                    type_str = "DEBIT"
                else:
                    amt_str = amts[0]

            if not type_str:
                p_cur = parse_amount(amt_str)
                if p_cur and p_cur[1]:
                    type_str = p_cur[1]

            reconstructed_rows.append([current_record["date"], desc, amt_str, type_str, bal_str])

    if len(reconstructed_rows) > 1:
        return normalize_table_rows(reconstructed_rows, use_ml=True)
    return []


_OCR_ENGINE = None


def get_ocr_engine():
    global _OCR_ENGINE
    if _OCR_ENGINE is None:
        if RapidOCR is None:
            raise RuntimeError("rapidocr_onnxruntime is not installed")
        _OCR_ENGINE = RapidOCR(use_angle_cls=False)
    return _OCR_ENGINE


def repair_date_str(s: str) -> str:
    s = s.strip()
    s = re.sub(r"\b(\d{2})(\d{2})[/.-](\d{4})\b", r"\1/\2/\3", s)
    s = re.sub(r"\b(\d{2})[-/.](\d{2})[-/.](\d{4})\b", r"\1/\2/\3", s)
    s = re.sub(r"\b(\d{4})[-/.](\d{2})[-/.](\d{2})\b", r"\1-\2-\3", s)
    return s


def is_amount(s: str) -> bool:
    cleaned = s.strip()
    CURR_PAT = r"(?:Rs\.?|INR|USD|EUR|GBP|CAD|AUD|NZD|CHF|SGD|HKD|JPY|SEK|NOK|DKK|PLN|ZAR|BRL|MXN|₹|\$|€|£|¥|kr)"
    cleaned = re.sub(r"^[+-]?" + CURR_PAT + r"\s*", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\s*" + CURR_PAT + r"\s*$", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\s*\b(DR|DEBIT|W/D|WITHDRAWAL|WDL|CR|CREDIT|DEP|DEPOSIT|Cr\.|Dr\.)\b\s*$", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"^\s*\b(DR|DEBIT|W/D|WITHDRAWAL|WDL|CR|CREDIT|DEP|DEPOSIT|Cr\.|Dr\.)\b\s*", "", cleaned, flags=re.IGNORECASE).strip()
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = cleaned[1:-1].strip()

    # Trailing / leading minus or plus
    cleaned = re.sub(r"[-–—\+]\s*$", "", cleaned).strip()
    cleaned = re.sub(r"^\s*[-–—\+]", "", cleaned).strip()

    # Strip Swiss apostrophes and multi-spaces
    cleaned = re.sub(r"(?<=\d)['’](?=\d)", "", cleaned)
    cleaned = re.sub(r"(?<=\d)[\s\u00A0]+(?=\d)", "", cleaned)

    if not re.match(r"^[+-]?[\d,\.]+$", cleaned):
        return False

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
        if cleaned.count(".") > 1:
            cleaned = cleaned.replace(".", "")

    if "." not in cleaned and len(cleaned) > 10:
        return False
    return bool(re.match(r"^[+-]?\d+(\.\d{1,2})?$", cleaned))


def parse_amt(s: str) -> Decimal:
    cleaned = s.strip()
    CURR_PAT = r"(?:Rs\.?|INR|USD|EUR|GBP|CAD|AUD|NZD|CHF|SGD|HKD|JPY|SEK|NOK|DKK|PLN|ZAR|BRL|MXN|₹|\$|€|£|¥|kr)"
    cleaned = re.sub(r"^[+-]?" + CURR_PAT + r"\s*", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\s*" + CURR_PAT + r"\s*$", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\s*\b(DR|DEBIT|W/D|WITHDRAWAL|WDL|CR|CREDIT|DEP|DEPOSIT|Cr\.|Dr\.)\b\s*$", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"^\s*\b(DR|DEBIT|W/D|WITHDRAWAL|WDL|CR|CREDIT|DEP|DEPOSIT|Cr\.|Dr\.)\b\s*", "", cleaned, flags=re.IGNORECASE).strip()
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = cleaned[1:-1].strip()

    # Trailing / leading minus or plus
    cleaned = re.sub(r"[-–—\+]\s*$", "", cleaned).strip()
    cleaned = re.sub(r"^\s*[-–—\+]", "", cleaned).strip()

    # Strip Swiss apostrophes and multi-spaces
    cleaned = re.sub(r"(?<=\d)['’](?=\d)", "", cleaned)
    cleaned = re.sub(r"(?<=\d)[\s\u00A0]+(?=\d)", "", cleaned)

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
        if cleaned.count(".") > 1:
            cleaned = cleaned.replace(".", "")

    cleaned = re.sub(r"[^\d.]", "", cleaned)
    if not cleaned:
        return Decimal("0.00")
    try:
        return Decimal(cleaned)
    except Exception:
        return Decimal("0.00")


def repair_balance(bal: Optional[Decimal], prev_bal: Optional[Decimal], amt: Decimal) -> Optional[Decimal]:
    if bal is None or prev_bal is None:
        return bal
    candidate = bal / Decimal("100")
    if abs((prev_bal - amt) - candidate) < Decimal("0.05") or abs((prev_bal + amt) - candidate) < Decimal("0.05"):
        return candidate
    return bal


def extract_raw_records_from_image_array(
    img_np: np.ndarray,
    running_balance: Optional[Decimal] = None
) -> Tuple[List[Dict[str, Any]], Optional[Decimal]]:
    try:
        ocr = get_ocr_engine()
        boxes, _ = ocr(img_np)
    except Exception as ex:
        logger.error(f"RapidOCR inference failed: {ex}")
        return [], running_balance

    if not boxes:
        return [], running_balance

    items: List[Dict[str, Any]] = []
    for box, text, score in boxes:
        text_clean = text.strip()
        if not text_clean:
            continue
        ymin = min(p[1] for p in box)
        ymax = max(p[1] for p in box)
        xmin = min(p[0] for p in box)
        xmax = max(p[0] for p in box)
        items.append({
            "ymin": ymin,
            "ymax": ymax,
            "yc": (ymin + ymax) / 2.0,
            "xmin": xmin,
            "xmax": xmax,
            "text": text_clean,
        })

    heights = [it["ymax"] - it["ymin"] for it in items]
    med_h = float(np.median(heights)) if heights else 14.0
    thresh = max(10.0, min(22.0, med_h * 0.75))

    items.sort(key=lambda it: it["yc"])
    lines: List[List[Dict[str, Any]]] = []
    for it in items:
        if not lines:
            lines.append([it])
        else:
            last_line = lines[-1]
            line_yc = sum(x["yc"] for x in last_line) / len(last_line)
            if abs(it["yc"] - line_yc) <= thresh:
                last_line.append(it)
            else:
                lines.append([it])

    all_dates: List[Tuple[int, int]] = []
    for line in lines:
        for it in line:
            rep = repair_date_str(it["text"])
            m = re.match(r"^(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?$", rep)
            if m:
                n1, n2 = int(m.group(1)), int(m.group(2))
                yr_part = m.group(3)
                if not yr_part and "." in rep and is_amount(rep):
                    continue
                if 1 <= n1 <= 31 and 1 <= n2 <= 31 and (n1 <= 12 or n2 <= 12):
                    all_dates.append((n1, n2))

    full_ocr_text = " ".join(it["text"] for it in items)

    # Detect Indian, UK, European or Commonwealth bank markers
    is_dayfirst_ocr = False
    if any(sym in full_ocr_text for sym in ("₹", "£", "€", "¥")):
        is_dayfirst_ocr = True
    elif re.search(
        r"\b(inr|rs|neft|rtgs|imps|upi|ifsc|gbp|sort\s*code|iban|bic|bsb|aud|nzd|sgd|chf|eur|euro|débit|crédit|solde|virement|libellé|buchung|buchungstag|soll|haben|saldo|valuta|wertstellung|cargo|abono|fecha|datum|omschrijving|af|bij)\b",
        full_ocr_text,
        re.IGNORECASE,
    ):
        is_dayfirst_ocr = True

    dayfirst = True
    if any(d[0] > 12 for d in all_dates):
        dayfirst = True
    elif any(d[1] > 12 for d in all_dates):
        dayfirst = False
    elif len(all_dates) >= 2:
        p1_vals = [d[0] for d in all_dates]
        p2_vals = [d[1] for d in all_dates]
        if len(set(p2_vals)) == 1 and len(set(p1_vals)) > 1:
            dayfirst = True
        elif len(set(p1_vals)) == 1 and len(set(p2_vals)) > 1:
            dayfirst = False
        elif is_dayfirst_ocr:
            dayfirst = True
    elif is_dayfirst_ocr:
        dayfirst = True

    MONTH_MAP = MULTILINGUAL_MONTH_MAP

    years = re.findall(r"(?<![\$\€\£\¥\₹\d\.,])(19\d\d|20[0-3]\d)(?!\.\d)", full_ocr_text)
    default_year = int(years[0]) if years else date.today().year

    m_stmt = re.search(r"\b([A-Za-z]{3,9})\s+\d{1,2},?\s+(20\d\d)\b", full_ocr_text)
    stmt_month = None
    if m_stmt:
        norm_m = unicodedata.normalize('NFKD', m_stmt.group(1)).encode('ASCII', 'ignore').decode('utf-8').lower()
        stmt_month = MONTH_MAP.get(norm_m)

    def extract_date(s: str) -> Optional[date]:
        rep = repair_date_str(s)
        # Named month: e.g. 15-Jan-2024, 15 Jan 2024, 15/Jan/2024 or 15-Jan
        m_named1 = re.match(r"^(\d{1,2})[-/.\s]([A-Za-z]{3,9})(?:[-/.\s](\d{2,4}))?$", rep)
        if m_named1:
            d_val, m_str = int(m_named1.group(1)), m_named1.group(2)
            m_clean = unicodedata.normalize('NFKD', m_str).encode('ASCII', 'ignore').decode('utf-8').lower()
            if m_clean in MONTH_MAP:
                m_val = MONTH_MAP[m_clean]
                yr_val = int(m_named1.group(3)) if m_named1.group(3) else None
                yr = (yr_val + 2000 if yr_val < 100 else yr_val) if yr_val else default_year
                if not yr_val and stmt_month and stmt_month < 6 and m_val > 6:
                    yr -= 1
                try:
                    return date(yr, m_val, d_val)
                except ValueError:
                    return None

        # Named month: e.g. Jan 15, 2024 or Jan-15-2024 or Jan 15
        m_named2 = re.match(r"^([A-Za-z]{3,9})[-/.\s](\d{1,2})(?:,?[-/.\s](\d{2,4}))?$", rep)
        if m_named2:
            m_str, d_val = m_named2.group(1), int(m_named2.group(2))
            m_clean = unicodedata.normalize('NFKD', m_str).encode('ASCII', 'ignore').decode('utf-8').lower()
            if m_clean in MONTH_MAP:
                m_val = MONTH_MAP[m_clean]
                yr_val = int(m_named2.group(3)) if m_named2.group(3) else None
                yr = (yr_val + 2000 if yr_val < 100 else yr_val) if yr_val else default_year
                if not yr_val and stmt_month and stmt_month < 6 and m_val > 6:
                    yr -= 1
                try:
                    return date(yr, m_val, d_val)
                except ValueError:
                    return None

        # Numeric dates: DD/MM/YYYY, MM/DD/YYYY or DD/MM, MM/DD
        m = re.match(r"^(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?$", rep)
        if m:
            n1, n2 = int(m.group(1)), int(m.group(2))
            yr_val = int(m.group(3)) if m.group(3) else None
            if not yr_val and "." in rep and is_amount(rep):
                return None
            if not (1 <= n1 <= 31 and 1 <= n2 <= 31 and (n1 <= 12 or n2 <= 12)):
                return None
            d_val, m_val = (n1, n2) if dayfirst else (n2, n1)
            if not (1 <= m_val <= 12 and 1 <= d_val <= 31):
                if 1 <= n1 <= 12 and 1 <= n2 <= 31:
                    d_val, m_val = n2, n1
                elif 1 <= n2 <= 12 and 1 <= n1 <= 31:
                    d_val, m_val = n1, n2
            if yr_val:
                yr = yr_val + 2000 if yr_val < 100 else yr_val
            else:
                yr = default_year
                if stmt_month and stmt_month < 6 and m_val > 6:
                    yr -= 1
            try:
                return date(yr, m_val, d_val)
            except ValueError:
                return None

        m_iso = re.match(r"^(\d{4})[/.-](\d{1,2})[/.-](\d{1,2})$", rep)
        if m_iso:
            try:
                return date(int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3)))
            except ValueError:
                return None
        return None

    # Detect initial opening balance if available
    for line in lines:
        texts = [x["text"] for x in line]
        full_text = " ".join(texts).upper()
        if (
            ("OPENING" in full_text and "BALANCE" in full_text)
            or "B/F" in full_text
            or "BROUGHT FORWARD" in full_text
            or "PREVIOUS BALANCE" in full_text
        ):
            amts = [parse_amt(x["text"]) for x in line if is_amount(x["text"])]
            if amts:
                running_balance = amts[-1]
                break

    SUMMARY_KEYWORDS = [
        "OPENING BALANCE",
        "CLOSING BALANCE",
        "TRANSACTION TOTAL",
        "TOTAL DR",
        "TOTAL CR",
        "CARRIED FORWARD",
        "BROUGHT FORWARD",
        "ANFANGSSALDO",
        "ENDSALDO",
        "ZWISCHENSUMME",
        "GESAMTSUMME",
        "UEBERTRAG",
        "ANCIEN SOLDE",
        "NOUVEAU SOLDE",
        "SOLDE INITIAL",
        "SOLDE FINAL",
        "SALDO ANTERIOR",
        "SALDO INICIAL",
        "SALDO FINAL",
        "SALDO INIZIALE",
        "SALDO FINALE",
        "VORIG SALDO",
        "NIEUW SALDO",
    ]

    records: List[Dict[str, Any]] = []
    for line in lines:
        line.sort(key=lambda x: x["xmin"])
        texts = [x["text"] for x in line]
        full_text = " ".join(texts).upper()
        if any(k in full_text for k in SUMMARY_KEYWORDS):
            continue

        date_objs = []
        non_date_items = []
        for it in line:
            d = extract_date(it["text"])
            if d:
                date_objs.append((d, it))
            else:
                non_date_items.append(it)

        if not date_objs:
            if records and not any(k in full_text for k in SUMMARY_KEYWORDS):
                HEADER_KEYWORDS = (
                    "DATE", "PARTICULARS", "NARRATION", "DEBIT", "CREDIT", "BALANCE", "AMOUNT",
                    "CHQ NO", "VALUE DATE", "STATEMENT", "ACCOUNT", "PAGE", "TRANSACTION HISTORY",
                    "REFERENCE NUMBER", "CHARGES", "BUCHUNG", "BUCHUNGSTAG", "SOLL", "HABEN",
                    "SALDO", "VORGANG", "VERWENDUNGSZWECK", "OPÉRATION", "OPERATION", "DÉBIT",
                    "CRÉDIT", "SOLDE", "LIBELLÉ", "LIBELLE", "FECHA", "CONCEPTO", "CARGO", "ABONO",
                    "DATUM", "OMSCHRIJVING", "AF", "BIJ", "DATA", "DESCRIZIONE", "IMPORTO",
                )
                is_header = any(k in full_text for k in HEADER_KEYWORDS)
                has_any_amount = any(is_amount(it["text"]) for it in line)
                if not is_header and not has_any_amount:
                    line_yc = sum(x["yc"] for x in line) / len(line)
                    if abs(line_yc - records[-1].get("_yc", line_yc)) <= thresh * 2.8:
                        extra_desc = " ".join(it["text"] for it in line).strip()
                        if extra_desc:
                            records[-1]["description"] = (records[-1]["description"] + " " + extra_desc).strip()
            continue

        txn_date = date_objs[0][0]
        amount_items = [it for it in non_date_items if is_amount(it["text"])]
        desc_items = [
            it
            for it in non_date_items
            if not is_amount(it["text"])
            and it["text"].upper() not in ("CR", "DR", "D3", "DEP", "WDL", "DEBIT", "CREDIT")
        ]
        type_hints = [
            it["text"]
            for it in non_date_items
            if it["text"].upper() in ("CR", "DR", "D3", "DEP", "WDL", "DEBIT", "CREDIT")
        ]

        # Opening balance line check: single amount, no description, and running_balance is None
        if len(amount_items) == 1 and not desc_items and running_balance is None:
            running_balance = parse_amt(amount_items[0]["text"])
            continue

        if not amount_items:
            continue

        if len(amount_items) == 1:
            txn_amount = parse_amt(amount_items[0]["text"])
            txn_bal = None
        elif len(amount_items) == 2:
            txn_amount = parse_amt(amount_items[0]["text"])
            raw_bal = parse_amt(amount_items[-1]["text"])
            txn_bal = repair_balance(raw_bal, running_balance, txn_amount)
        else:
            raw_bal = parse_amt(amount_items[-1]["text"])
            candidates = [parse_amt(x["text"]) for x in amount_items[:-1]]
            non_zeros = [c for c in candidates if c > Decimal("0")]
            if len(non_zeros) == 1:
                txn_amount = non_zeros[0]
            elif running_balance is not None:
                delta = abs(raw_bal - running_balance)
                txn_amount = min(candidates, key=lambda c: abs(c - delta))
            else:
                txn_amount = non_zeros[0] if non_zeros else candidates[0]
            txn_bal = repair_balance(raw_bal, running_balance, txn_amount)

        description = " ".join(it["text"] for it in desc_items).strip() or "Unlabeled Transaction"

        txn_type = None
        # 1. Running balance delta inference
        if txn_bal is not None and running_balance is not None:
            delta = txn_bal - running_balance
            if delta > Decimal("0.01"):
                txn_type = "CREDIT"
            elif delta < -Decimal("0.01"):
                txn_type = "DEBIT"

        # 2. Type hints from OCR token if running balance delta was not applicable
        if not txn_type and type_hints:
            th = type_hints[0].upper()
            if any(k in th for k in ("CR", "CREDIT", "DEP")):
                txn_type = "CREDIT"
            elif any(k in th for k in ("DR", "DEBIT", "D3", "WDL")):
                txn_type = "DEBIT"

        # 3. Description keyword guardrails
        if not txn_type:
            if re.search(r"\b(salary|stipend|dividend|refund|payroll|bonus|direct\s*deposit|deposit)\b", description, re.IGNORECASE):
                txn_type = "CREDIT"
            else:
                txn_type = "DEBIT"

        if txn_bal is not None:
            running_balance = txn_bal

        line_yc = sum(x["yc"] for x in line) / len(line)
        records.append({
            "txn_date": txn_date,
            "description": description,
            "amount": txn_amount,
            "balance": txn_bal,
            "txn_type": txn_type,
            "_yc": line_yc,
        })

    for r in records:
        r.pop("_yc", None)

    return records, running_balance


def extract_transactions_from_images(img_arrays: List[np.ndarray]) -> List[TransactionCreate]:
    """
    Given page image numpy arrays, run OCR, line clustering, running balance delta inference,
    categorization, and return validated TransactionCreate instances.
    """
    all_raw: List[Dict[str, Any]] = []
    running_balance: Optional[Decimal] = None
    for img_np in img_arrays:
        page_records, running_balance = extract_raw_records_from_image_array(img_np, running_balance)
        all_raw.extend(page_records)

    if not all_raw:
        return []

    batch_results = categorize_transactions_batch(
        [r["description"] for r in all_raw],
        [r["txn_type"] for r in all_raw],
    )

    txns: List[TransactionCreate] = []
    for r, b_res in zip(all_raw, batch_results):
        row_h = compute_row_hash(r["txn_date"], r["description"], r["amount"], r["balance"])
        txns.append(
            TransactionCreate(
                txn_date=r["txn_date"],
                description=r["description"],
                amount=r["amount"],
                txn_type=r["txn_type"],
                category=b_res.category,
                category_confidence=b_res.confidence,
                category_source=b_res.source,
                balance=r["balance"],
                row_hash=row_h,
            )
        )
    return txns


def extract_tables_from_image(image_bytes: bytes, filename: str = "statement.jpg") -> List[TransactionCreate]:
    """
    Extracts tabular transactions from direct image uploads (JPG, PNG, WebP) using RapidOCR.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode != "RGB":
            img = img.convert("RGB")
        img_np = np.array(img)
    except Exception as ex:
        logger.error(f"Failed to load image for table extraction: {ex}")
        return []

    return extract_transactions_from_images([img_np])
