import io
import os
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from PIL import Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import Base, get_db
from app.main import app
from app.models import ForecastRun, Statement, Transaction
from app.services.pdf_extractor import extract_tables_from_pdf


# Test async engine using in-memory SQLite isolated for E2E scenarios
e2e_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    echo=False,
    future=True,
)
E2ESessionLocal = async_sessionmaker(
    bind=e2e_engine,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def override_e2e_get_db():
    async with E2ESessionLocal() as session:
        yield session


@pytest_asyncio.fixture(autouse=True)
async def setup_e2e_db():
    prev_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_e2e_get_db
    async with e2e_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with e2e_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    if prev_override is not None:
        app.dependency_overrides[get_db] = prev_override
    else:
        app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Test Artifact Generators & Verification Resources
# ---------------------------------------------------------------------------
SAMPLE_1_PDF_PATH = "/home/sarthakroutray/Downloads/1.pdf"
_IMAGE_CACHE = {}


def get_scanned_pdf_bytes() -> bytes:
    """Retrieve raw bytes of official Axis Bank verification sample 1.pdf."""
    assert os.path.exists(SAMPLE_1_PDF_PATH), f"Verification oracle {SAMPLE_1_PDF_PATH} does not exist"
    with open(SAMPLE_1_PDF_PATH, "rb") as f:
        return f.read()


def get_scanned_image_bytes(format_name: str = "PNG") -> bytes:
    """Convert page 1 of 1.pdf to raster image bytes (PNG, JPEG, WEBP) via pdf2image."""
    fmt = format_name.upper()
    if fmt == "JPG":
        fmt = "JPEG"
    if fmt in _IMAGE_CACHE:
        return _IMAGE_CACHE[fmt]

    from pdf2image import convert_from_bytes
    pdf_bytes = get_scanned_pdf_bytes()
    images = convert_from_bytes(pdf_bytes)
    assert len(images) > 0, "Failed to render scanned PDF page to raster image"

    buf = io.BytesIO()
    images[0].save(buf, format=fmt)
    data = buf.getvalue()
    _IMAGE_CACHE[fmt] = data
    return data


def generate_digital_pdf(custom_rows: Optional[List[List[str]]] = None) -> bytes:
    """Generate a standard text-layer PDF bank statement using ReportLab."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    elements.append(Paragraph("Account Activity Statement", styles["Heading1"]))

    table_data = [
        ["Date", "Description", "Debit", "Credit", "Balance"],
        ["2024-01-05", "Starbucks Store #991", "6.50", "", "1200.00"],
        ["2024-01-06", "Whole Foods Market", "82.30", "", "1117.70"],
        ["2024-01-07", "Payroll Direct Deposit", "", "2500.00", "3617.70"],
        ["2024-01-08", "PG&E Electric Bill", "95.00", "", "3522.70"],
        ["2024-01-09", "Uber Trip to Downtown", "24.50", "", "3498.20"],
        ["2024-01-10", "Netflix Subscription", "15.99", "", "3482.21"],
    ]
    if custom_rows:
        table_data = custom_rows

    t = Table(table_data)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(t)
    doc.build(elements)
    return buf.getvalue()


def generate_blank_pdf() -> bytes:
    """Generate an empty PDF containing no tabular data or visible text."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter)
    styles = getSampleStyleSheet()
    doc.build([Paragraph("   ", styles["Normal"])])
    return buf.getvalue()


def generate_blank_image(format_name: str = "PNG") -> bytes:
    """Generate a solid white image containing zero text or transaction rows."""
    fmt = format_name.upper()
    if fmt == "JPG":
        fmt = "JPEG"
    img = Image.new("RGB", (100, 100), color="white")
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


# ===========================================================================
# TIER 1: FEATURE COVERAGE (Isolated Happy Path >= 5 tests per feature)
# ===========================================================================

# --- Feature 1: Scanned Image PDF Extraction via OCR Fallback (F1 / R1) ---

@pytest.mark.asyncio
async def test_tier1_f1_scanned_pdf_upload_endpoint():
    """Upload scanned PDF 1.pdf; verify HTTP 201, COMPLETED status, and >=10 rows extracted."""
    pdf_bytes = get_scanned_pdf_bytes()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        files = {"file": ("1.pdf", pdf_bytes, "application/pdf")}
        resp = await ac.post("/api/v1/statements/upload", files=files)
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["status"] == "COMPLETED"
        assert data["statement"]["row_count"] >= 10
        assert data["newly_inserted"] >= 10
        assert len(data["parsed_rows"]) >= 10


@pytest.mark.asyncio
async def test_tier1_f1_scanned_pdf_direct_extractor_service():
    """Direct call to extract_tables_from_pdf on 1.pdf yields exactly 13 transactions."""
    pdf_bytes = get_scanned_pdf_bytes()
    txns = extract_tables_from_pdf(pdf_bytes, filename="1.pdf")
    assert isinstance(txns, list)
    assert len(txns) == 13, f"Expected 13 transactions from 1.pdf oracle, got {len(txns)}"


@pytest.mark.asyncio
async def test_tier1_f1_scanned_pdf_debit_credit_classification():
    """Verify exactly 11 DEBIT and 2 CREDIT transactions classified via balance delta inference."""
    pdf_bytes = get_scanned_pdf_bytes()
    txns = extract_tables_from_pdf(pdf_bytes, filename="1.pdf")
    debits = [t for t in txns if t.txn_type == "DEBIT"]
    credits = [t for t in txns if t.txn_type == "CREDIT"]
    assert len(debits) == 11, f"Expected 11 DEBIT transactions, got {len(debits)}"
    assert len(credits) == 2, f"Expected 2 CREDIT transactions, got {len(credits)}"


@pytest.mark.asyncio
async def test_tier1_f1_scanned_pdf_row_hash_uniqueness():
    """Verify all 13 transactions from 1.pdf have deterministic, non-empty, unique row_hashes."""
    pdf_bytes = get_scanned_pdf_bytes()
    txns = extract_tables_from_pdf(pdf_bytes, filename="1.pdf")
    hashes = [t.row_hash for t in txns]
    assert len(hashes) == 13
    assert all(isinstance(h, str) and len(h) >= 32 for h in hashes)
    assert len(set(hashes)) == 13, "Duplicate row_hash detected among extracted transactions"


@pytest.mark.asyncio
async def test_tier1_f1_scanned_pdf_duplicate_upload_deduplication():
    """Uploading 1.pdf twice yields newly_inserted=0 and skips all duplicates on second upload."""
    pdf_bytes = get_scanned_pdf_bytes()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        files1 = {"file": ("1.pdf", pdf_bytes, "application/pdf")}
        resp1 = await ac.post("/api/v1/statements/upload", files=files1)
        assert resp1.status_code == 201
        data1 = resp1.json()
        initial_inserted = data1["newly_inserted"]
        assert initial_inserted >= 10

        files2 = {"file": ("1_duplicate.pdf", pdf_bytes, "application/pdf")}
        resp2 = await ac.post("/api/v1/statements/upload", files=files2)
        assert resp2.status_code == 201
        data2 = resp2.json()
        assert data2["newly_inserted"] == 0
        assert data2["duplicates_skipped"] == initial_inserted


# --- Feature 2: Direct Image Upload Ingestion (JPG, JPEG, PNG, WebP) (F2 / R1) ---

@pytest.mark.asyncio
async def test_tier1_f2_direct_image_upload_png():
    """Upload PNG statement image; verify HTTP 201, COMPLETED status, and newly_inserted >= 10."""
    png_bytes = get_scanned_image_bytes("PNG")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        files = {"file": ("statement.png", png_bytes, "image/png")}
        resp = await ac.post("/api/v1/statements/upload", files=files)
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["status"] == "COMPLETED"
        assert data["newly_inserted"] >= 10


@pytest.mark.asyncio
async def test_tier1_f2_direct_image_upload_jpeg():
    """Upload JPEG statement image; verify HTTP 201, COMPLETED status, and newly_inserted >= 10."""
    jpg_bytes = get_scanned_image_bytes("JPEG")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        files = {"file": ("statement.jpg", jpg_bytes, "image/jpeg")}
        resp = await ac.post("/api/v1/statements/upload", files=files)
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["status"] == "COMPLETED"
        assert data["newly_inserted"] >= 10


@pytest.mark.asyncio
async def test_tier1_f2_direct_image_upload_webp():
    """Upload WebP statement image; verify HTTP 201, COMPLETED status, and newly_inserted >= 10."""
    webp_bytes = get_scanned_image_bytes("WEBP")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        files = {"file": ("statement.webp", webp_bytes, "image/webp")}
        resp = await ac.post("/api/v1/statements/upload", files=files)
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["status"] == "COMPLETED"
        assert data["newly_inserted"] >= 10


@pytest.mark.asyncio
async def test_tier1_f2_image_direct_extractor_service():
    """Direct call to extract_tables_from_image returns >=10 normalized TransactionCreate items."""
    try:
        from app.services.pdf_extractor import extract_tables_from_image
    except ImportError:
        pytest.fail("app.services.pdf_extractor does not export extract_tables_from_image")

    png_bytes = get_scanned_image_bytes("PNG")
    txns = extract_tables_from_image(png_bytes, filename="test.png")
    assert isinstance(txns, list)
    assert len(txns) >= 10, f"Expected >=10 transactions from image OCR, got {len(txns)}"


@pytest.mark.asyncio
async def test_tier1_f2_image_upload_case_insensitive_extension():
    """Upload image with uppercase extension (e.g. .PNG, .JPG); assert HTTP 201 acceptance."""
    png_bytes = get_scanned_image_bytes("PNG")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        files = {"file": ("STATEMENT_UPPER.PNG", png_bytes, "image/png")}
        resp = await ac.post("/api/v1/statements/upload", files=files)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "COMPLETED"


# --- Feature 3: Digital Text PDF Non-Regression (F3 / R1) ---

@pytest.mark.asyncio
async def test_tier1_f3_digital_pdf_upload_table_extraction():
    """Upload digital PDF with 6 transactions; assert 201 Created and newly_inserted == 6."""
    pdf_bytes = generate_digital_pdf()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        files = {"file": ("digital_stmt.pdf", pdf_bytes, "application/pdf")}
        resp = await ac.post("/api/v1/statements/upload", files=files)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "COMPLETED"
        assert data["newly_inserted"] == 6
        assert len(data["parsed_rows"]) == 6


@pytest.mark.asyncio
async def test_tier1_f3_digital_pdf_direct_extractor_service():
    """Direct call to extract_tables_from_pdf on digital PDF returns exactly 6 transactions."""
    pdf_bytes = generate_digital_pdf()
    txns = extract_tables_from_pdf(pdf_bytes, filename="digital.pdf")
    assert len(txns) == 6


@pytest.mark.asyncio
async def test_tier1_f3_digital_pdf_descriptions_and_amounts():
    """Verify exact amounts and merchant descriptions match source table in digital PDF."""
    pdf_bytes = generate_digital_pdf()
    txns = extract_tables_from_pdf(pdf_bytes, filename="digital.pdf")
    desc_to_amt = {t.description: float(t.amount) for t in txns}
    assert any("Starbucks" in d for d in desc_to_amt)
    assert any("Whole Foods" in d for d in desc_to_amt)
    assert any("Payroll" in d for d in desc_to_amt)
    starbucks_amt = next(amt for d, amt in desc_to_amt.items() if "Starbucks" in d)
    assert starbucks_amt == pytest.approx(6.50, rel=1e-2)


@pytest.mark.asyncio
async def test_tier1_f3_digital_pdf_credit_debit_types():
    """Verify Payroll is categorized as CREDIT and expense rows are DEBIT."""
    pdf_bytes = generate_digital_pdf()
    txns = extract_tables_from_pdf(pdf_bytes, filename="digital.pdf")
    payroll = next(t for t in txns if "Payroll" in t.description)
    assert payroll.txn_type == "CREDIT"
    expenses = [t for t in txns if "Payroll" not in t.description]
    assert all(t.txn_type == "DEBIT" for t in expenses)
    assert len(expenses) == 5


@pytest.mark.asyncio
async def test_tier1_f3_digital_pdf_running_balances():
    """Verify running balance values match source table in digital PDF."""
    pdf_bytes = generate_digital_pdf()
    txns = extract_tables_from_pdf(pdf_bytes, filename="digital.pdf")
    starbucks = next(t for t in txns if "Starbucks" in t.description)
    assert starbucks.balance is not None
    assert float(starbucks.balance) == pytest.approx(1200.00, rel=1e-2)


# --- Feature 4: Backend API Empty State Graceful Handling (F4 / R2) ---

@pytest.mark.asyncio
async def test_tier1_f4_forecast_generate_empty_db_returns_200():
    """POST /forecasts/generate on empty DB must return HTTP 200 with status=EMPTY."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/v1/forecasts/generate", json={"granularity": "DAILY", "horizon": 30})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["status"] == "EMPTY"
        assert data["forecast_payload"] == []
        assert data["historical_series"] == []


@pytest.mark.asyncio
async def test_tier1_f4_forecast_latest_empty_db_returns_200():
    """GET /forecasts/latest on empty DB must return HTTP 200 with status=EMPTY."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/forecasts/latest?granularity=DAILY&horizon=30")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["status"] == "EMPTY"
        assert data["forecast_payload"] == []
        assert data["historical_series"] == []


@pytest.mark.asyncio
async def test_tier1_f4_forecast_generate_zero_debit_credits_only_returns_200():
    """POST /forecasts/generate when database contains only CREDIT transactions returns HTTP 200 EMPTY."""
    async with E2ESessionLocal() as session:
        stmt = Statement(
            filename="credits_only.pdf",
            status="COMPLETED",
            total_credit=Decimal("5000.00"),
            total_debit=Decimal("0.00"),
            row_count=1
        )
        session.add(stmt)
        await session.flush()
        txn = Transaction(
            statement_id=stmt.id,
            txn_date=date(2024, 1, 15),
            description="Client Consulting Retainer Direct Deposit",
            amount=Decimal("5000.00"),
            txn_type="CREDIT",
            category="Income",
            row_hash="test_credit_only_hash_001"
        )
        session.add(txn)
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/v1/forecasts/generate", json={"granularity": "DAILY", "horizon": 14})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["status"] == "EMPTY"
        assert data["forecast_payload"] == []


@pytest.mark.asyncio
async def test_tier1_f4_forecast_latest_zero_debit_credits_only_returns_200():
    """GET /forecasts/latest when database contains only CREDIT transactions returns HTTP 200 EMPTY."""
    async with E2ESessionLocal() as session:
        stmt = Statement(
            filename="credits_only.pdf",
            status="COMPLETED",
            total_credit=Decimal("3000.00"),
            total_debit=Decimal("0.00"),
            row_count=1
        )
        session.add(stmt)
        await session.flush()
        txn = Transaction(
            statement_id=stmt.id,
            txn_date=date(2024, 1, 15),
            description="Performance Bonus Deposit",
            amount=Decimal("3000.00"),
            txn_type="CREDIT",
            category="Income",
            row_hash="test_credit_only_hash_002"
        )
        session.add(txn)
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/forecasts/latest?granularity=DAILY&horizon=14")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["status"] == "EMPTY"
        assert data["forecast_payload"] == []


@pytest.mark.asyncio
async def test_tier1_f4_forecast_generate_transfers_only_returns_200():
    """POST /forecasts/generate when debits are only 'Transfers' returns HTTP 200 EMPTY."""
    async with E2ESessionLocal() as session:
        stmt = Statement(
            filename="transfers_only.pdf",
            status="COMPLETED",
            total_debit=Decimal("1500.00"),
            total_credit=Decimal("0.00"),
            row_count=1
        )
        session.add(stmt)
        await session.flush()
        txn = Transaction(
            statement_id=stmt.id,
            txn_date=date(2024, 1, 15),
            description="Transfer to Savings Acct #4492",
            amount=Decimal("1500.00"),
            txn_type="DEBIT",
            category="Transfers",
            row_hash="test_transfer_only_hash_001"
        )
        session.add(txn)
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/v1/forecasts/generate", json={"granularity": "DAILY", "horizon": 14})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["status"] == "EMPTY"
        assert data["forecast_payload"] == []


@pytest.mark.asyncio
async def test_tier1_f4_forecast_latest_transfers_only_returns_200():
    """GET /forecasts/latest when debits are only 'Transfers' returns HTTP 200 EMPTY."""
    async with E2ESessionLocal() as session:
        stmt = Statement(
            filename="transfers_only.pdf",
            status="COMPLETED",
            total_debit=Decimal("1500.00"),
            total_credit=Decimal("0.00"),
            row_count=1
        )
        session.add(stmt)
        await session.flush()
        txn = Transaction(
            statement_id=stmt.id,
            txn_date=date(2024, 1, 15),
            description="Transfer to Brokerage Acct",
            amount=Decimal("1500.00"),
            txn_type="DEBIT",
            category="Transfers",
            row_hash="test_transfer_only_hash_002"
        )
        session.add(txn)
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/forecasts/latest?granularity=DAILY&horizon=14")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["status"] == "EMPTY"
        assert data["forecast_payload"] == []


# ===========================================================================
# TIER 2: BOUNDARY & CORNER CASES (>= 5 tests per feature area)
# ===========================================================================

# --- Ingestion Boundaries ---

@pytest.mark.asyncio
async def test_tier2_upload_empty_file_zero_bytes():
    """Uploading an empty 0-byte file yields 0 extracted rows or graceful 400."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        files = {"file": ("empty.pdf", b"", "application/pdf")}
        resp = await ac.post("/api/v1/statements/upload", files=files)
        assert resp.status_code in [201, 400]
        if resp.status_code == 201:
            data = resp.json()
            assert data["newly_inserted"] == 0
            assert data["parsed_rows"] == []


@pytest.mark.asyncio
async def test_tier2_upload_blank_digital_pdf():
    """Uploading a blank PDF (0 rows) returns 201 with newly_inserted=0 and parsed_rows=[]."""
    blank_pdf = generate_blank_pdf()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        files = {"file": ("blank.pdf", blank_pdf, "application/pdf")}
        resp = await ac.post("/api/v1/statements/upload", files=files)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "COMPLETED"
        assert data["newly_inserted"] == 0
        assert data["parsed_rows"] == []


@pytest.mark.asyncio
async def test_tier2_upload_blank_image():
    """Uploading a blank solid white image returns 201 with newly_inserted=0 and parsed_rows=[]."""
    blank_img = generate_blank_image("PNG")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        files = {"file": ("blank.png", blank_img, "image/png")}
        resp = await ac.post("/api/v1/statements/upload", files=files)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "COMPLETED"
        assert data["newly_inserted"] == 0
        assert data["parsed_rows"] == []


@pytest.mark.asyncio
async def test_tier2_upload_unsupported_extensions():
    """Uploading files with unsupported extensions returns HTTP 400 Bad Request."""
    unsupported = [
        ("report.txt", b"plain text content", "text/plain"),
        ("transactions.csv", b"Date,Amount\n2024-01-01,10.00", "text/csv"),
        ("document.docx", b"word binary stream", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ("malware.exe", b"MZ executable header", "application/x-msdownload"),
    ]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        for fname, content, mime in unsupported:
            files = {"file": (fname, content, mime)}
            resp = await ac.post("/api/v1/statements/upload", files=files)
            assert resp.status_code == 400
            assert "Invalid file format" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_tier2_upload_corrupted_pdf_stream():
    """Uploading random corrupt bytes with .pdf extension is handled gracefully without crash."""
    corrupt_bytes = b"%PDF-1.4\nTRUNCATED_AND_CORRUPTED_STREAM_XYZ12345"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        files = {"file": ("corrupt.pdf", corrupt_bytes, "application/pdf")}
        resp = await ac.post("/api/v1/statements/upload", files=files)
        assert resp.status_code in [201, 400, 500]


@pytest.mark.asyncio
async def test_tier2_upload_corrupted_image_stream():
    """Uploading random corrupt bytes with .png extension is handled gracefully without crash."""
    corrupt_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR_MALFORMED"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        files = {"file": ("corrupt.png", corrupt_bytes, "image/png")}
        resp = await ac.post("/api/v1/statements/upload", files=files)
        assert resp.status_code in [201, 400, 500]


@pytest.mark.asyncio
async def test_tier2_upload_filename_with_special_chars():
    """Uploading file with spaces, parentheses, brackets, and hashes in filename succeeds."""
    pdf_bytes = generate_digital_pdf()
    special_name = "Axis Bank Stmt #1 (April 2019) [Confidential] & scanned.pdf"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        files = {"file": (special_name, pdf_bytes, "application/pdf")}
        resp = await ac.post("/api/v1/statements/upload", files=files)
        assert resp.status_code == 201
        data = resp.json()
        assert data["statement"]["filename"] == special_name


# --- API Empty & Limit Boundaries ---

@pytest.mark.asyncio
async def test_tier2_analytics_summary_empty_database():
    """GET /analytics/summary on empty DB returns HTTP 200 with zero totals and burn rate."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/analytics/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_spend_historical_30d"] == 0.0
        assert data["daily_avg_burn_rate"] == 0.0
        assert data["top_categories"] == []


@pytest.mark.asyncio
async def test_tier2_transactions_list_empty_database():
    """GET /transactions on empty DB returns HTTP 200 with empty items list and total=0."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/transactions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0


@pytest.mark.asyncio
async def test_tier2_patch_category_nonexistent_transaction_id():
    """PATCH /transactions/{random_uuid}/category returns HTTP 404 Not Found."""
    random_id = str(uuid.uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.patch(f"/api/v1/transactions/{random_id}/category", json={"category": "Groceries"})
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_tier2_forecast_generate_invalid_granularity_rejected():
    """POST /forecasts/generate with invalid granularity is rejected with 422 Unprocessable Entity."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/v1/forecasts/generate", json={"granularity": "HOURLY", "horizon": 14})
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_tier2_forecast_generate_horizon_boundary_limits():
    """POST /forecasts/generate handles horizon boundaries (H=1 and H=365) correctly."""
    pdf_bytes = generate_digital_pdf()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        upload_resp = await ac.post("/api/v1/statements/upload", files={"file": ("stmt.pdf", pdf_bytes, "application/pdf")})
        assert upload_resp.status_code == 201

        # Minimum horizon = 1
        resp_h1 = await ac.post("/api/v1/forecasts/generate", json={"granularity": "DAILY", "horizon": 1})
        assert resp_h1.status_code == 200
        assert len(resp_h1.json()["forecast_payload"]) == 1

        # Large horizon = 365
        resp_h365 = await ac.post("/api/v1/forecasts/generate", json={"granularity": "DAILY", "horizon": 365})
        assert resp_h365.status_code == 200
        assert len(resp_h365.json()["forecast_payload"]) == 365


# ===========================================================================
# TIER 3: CROSS-FEATURE INTERACTIONS (Multi-format & Lifecycle flows)
# ===========================================================================

@pytest.mark.asyncio
async def test_tier3_lifecycle_empty_to_uploaded_to_forecasted():
    """Full lifecycle: empty DB (200 EMPTY) -> statement upload -> transactions listed -> SARIMA refit -> latest forecast retrieval."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Initial state: Empty DB returns HTTP 200 with status=EMPTY
        r_init = await ac.get("/api/v1/forecasts/latest")
        assert r_init.status_code == 200
        assert r_init.json()["status"] == "EMPTY"

        # 2. Upload statement
        pdf_bytes = generate_digital_pdf()
        r_upload = await ac.post("/api/v1/statements/upload", files={"file": ("stmt.pdf", pdf_bytes, "application/pdf")})
        assert r_upload.status_code == 201
        assert r_upload.json()["newly_inserted"] == 6

        # 3. Retrieve transactions
        r_txns = await ac.get("/api/v1/transactions")
        assert r_txns.status_code == 200
        assert r_txns.json()["total"] == 6

        # 4. Fit forecast
        r_forecast = await ac.post("/api/v1/forecasts/generate", json={"granularity": "DAILY", "horizon": 14})
        assert r_forecast.status_code == 200
        f_data = r_forecast.json()
        assert len(f_data["forecast_payload"]) == 14
        f_id = f_data["forecast_id"]

        # 5. Get latest forecast
        r_latest = await ac.get("/api/v1/forecasts/latest?granularity=DAILY&horizon=14")
        assert r_latest.status_code == 200
        assert r_latest.json()["forecast_id"] == f_id


@pytest.mark.asyncio
async def test_tier3_scanned_pdf_upload_then_category_override_then_analytics():
    """Upload scanned PDF 1.pdf -> override transaction category -> verify analytics summary reflects changes."""
    pdf_bytes = get_scanned_pdf_bytes()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        upload_resp = await ac.post("/api/v1/statements/upload", files={"file": ("1.pdf", pdf_bytes, "application/pdf")})
        assert upload_resp.status_code == 201

        # Fetch transaction items
        txns_resp = await ac.get("/api/v1/transactions?page_size=20")
        assert txns_resp.status_code == 200
        items = txns_resp.json()["items"]
        assert len(items) >= 10
        target_txn = items[0]

        # Patch category
        new_category = "HVAC Equipment & Maintenance"
        patch_resp = await ac.patch(
            f"/api/v1/transactions/{target_txn['id']}/category",
            json={"category": new_category}
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["category"] == new_category

        # Fetch analytics summary
        summary_resp = await ac.get("/api/v1/analytics/summary")
        assert summary_resp.status_code == 200
        summary_data = summary_resp.json()
        top_cats = [c["category"] for c in summary_data["top_categories"]]
        assert new_category in top_cats


@pytest.mark.asyncio
async def test_tier3_multi_format_sequential_uploads_unified_ledger():
    """Upload digital PDF + direct PNG image + duplicate scanned PDF -> unified ledger aggregates and dedupes accurately."""
    digital_pdf = generate_digital_pdf()
    png_bytes = get_scanned_image_bytes("PNG")
    scanned_pdf = get_scanned_pdf_bytes()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Upload digital PDF (6 rows)
        r1 = await ac.post("/api/v1/statements/upload", files={"file": ("digital.pdf", digital_pdf, "application/pdf")})
        assert r1.status_code == 201
        count1 = r1.json()["newly_inserted"]
        assert count1 == 6

        # 2. Upload PNG raster (>=10 rows)
        r2 = await ac.post("/api/v1/statements/upload", files={"file": ("scanned.png", png_bytes, "image/png")})
        assert r2.status_code == 201
        count2 = r2.json()["newly_inserted"]
        assert count2 >= 10

        # 3. Upload duplicate scanned PDF (should deduplicate transactions matching png_bytes)
        r3 = await ac.post("/api/v1/statements/upload", files={"file": ("scanned_copy.pdf", scanned_pdf, "application/pdf")})
        assert r3.status_code == 201
        # Any rows with matching row_hashes will be skipped
        data3 = r3.json()
        assert data3["status"] == "COMPLETED"

        # 4. Check unified transaction count
        r_all = await ac.get("/api/v1/transactions?page_size=100")
        assert r_all.status_code == 200
        total_txns = r_all.json()["total"]
        assert total_txns >= count1 + count2


@pytest.mark.asyncio
async def test_tier3_credits_only_then_debit_upload_unlocks_forecasting():
    """Insert only CREDIT transactions (forecast EMPTY) -> upload debit statement -> forecast unlocks and succeeds."""
    # Seed credit transaction
    async with E2ESessionLocal() as session:
        stmt = Statement(filename="credits.pdf", status="COMPLETED", total_credit=Decimal("10000.00"), total_debit=Decimal("0.00"), row_count=1)
        session.add(stmt)
        await session.flush()
        txn = Transaction(
            statement_id=stmt.id,
            txn_date=date(2024, 1, 1),
            description="Seed Capital Deposit",
            amount=Decimal("10000.00"),
            txn_type="CREDIT",
            category="Income",
            row_hash="test_credit_seed_001"
        )
        session.add(txn)
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Forecast before debit upload is EMPTY
        r_before = await ac.post("/api/v1/forecasts/generate", json={"granularity": "DAILY", "horizon": 14})
        assert r_before.status_code == 200
        assert r_before.json()["status"] == "EMPTY"

        # Upload debit statement
        pdf_bytes = generate_digital_pdf()
        r_upload = await ac.post("/api/v1/statements/upload", files={"file": ("debits.pdf", pdf_bytes, "application/pdf")})
        assert r_upload.status_code == 201

        # Forecast after debit upload succeeds
        r_after = await ac.post("/api/v1/forecasts/generate", json={"granularity": "DAILY", "horizon": 14})
        assert r_after.status_code == 200
        assert len(r_after.json()["forecast_payload"]) == 14


@pytest.mark.asyncio
async def test_tier3_analytics_summary_matches_aggregated_transactions():
    """Upload statement; verify /analytics/summary total_spend matches sum of individual DEBIT transactions."""
    pdf_bytes = generate_digital_pdf()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await ac.post("/api/v1/statements/upload", files={"file": ("stmt.pdf", pdf_bytes, "application/pdf")})

        txns_resp = await ac.get("/api/v1/transactions?page_size=100")
        assert txns_resp.status_code == 200
        items = txns_resp.json()["items"]
        computed_debit_sum = sum(
            float(t["amount"]) for t in items if t["txn_type"] == "DEBIT" and t["category"] != "Transfers"
        )

        summary_resp = await ac.get("/api/v1/analytics/summary")
        assert summary_resp.status_code == 200
        summary_spend = summary_resp.json()["total_spend_historical_30d"]
        assert summary_spend == pytest.approx(computed_debit_sum, rel=1e-2)


# ===========================================================================
# TIER 4: REAL-WORLD APPLICATION SCENARIOS (>= 5 scenarios)
# ===========================================================================

@pytest.mark.asyncio
async def test_tier4_scenario_first_time_user_onboarding_zero_state():
    """Scenario 1: New user opens app for the first time on an empty database. All dashboard calls return clean 200s with zero console/network errors."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # User checks backend health
        health_resp = await ac.get("/health")
        assert health_resp.status_code == 200
        assert health_resp.json()["status"] == "healthy"

        # User loads summary analytics
        summary_resp = await ac.get("/api/v1/analytics/summary")
        assert summary_resp.status_code == 200
        summary = summary_resp.json()
        assert summary["total_spend_historical_30d"] == 0.0
        assert summary["top_categories"] == []

        # User fetches latest forecast
        forecast_resp = await ac.get("/api/v1/forecasts/latest?granularity=DAILY&horizon=30")
        assert forecast_resp.status_code == 200
        assert forecast_resp.json()["status"] == "EMPTY"
        assert forecast_resp.json()["forecast_payload"] == []

        # User views transaction table
        txns_resp = await ac.get("/api/v1/transactions?page=1&page_size=15")
        assert txns_resp.status_code == 200
        assert txns_resp.json()["total"] == 0
        assert txns_resp.json()["items"] == []


@pytest.mark.asyncio
async def test_tier4_scenario_business_owner_scanned_statement_reconciliation():
    """Scenario 2: Business owner uploads Axis Bank scanned PDF (1.pdf); validates 13 rows, high-value credits, and analytics metrics."""
    pdf_bytes = get_scanned_pdf_bytes()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Upload scanned document
        upload_resp = await ac.post("/api/v1/statements/upload", files={"file": ("axis_statement_apr2019.pdf", pdf_bytes, "application/pdf")})
        assert upload_resp.status_code == 201
        upload_data = upload_resp.json()
        assert upload_data["status"] == "COMPLETED"
        assert upload_data["newly_inserted"] == 13

        # 2. Reconcile transactions
        txns_resp = await ac.get("/api/v1/transactions?page_size=50")
        assert txns_resp.status_code == 200
        txns = txns_resp.json()["items"]
        assert len(txns) == 13

        # Verify business high-value credits ($362,700 and $10,000)
        credits = [t for t in txns if t["txn_type"] == "CREDIT"]
        assert len(credits) == 2
        credit_amounts = sorted([float(c["amount"]) for c in credits])
        assert credit_amounts[0] == pytest.approx(10000.00, rel=1e-2)
        assert credit_amounts[1] == pytest.approx(362700.00, rel=1e-2)

        # 3. Check analytics summary captures transaction volume
        summary_resp = await ac.get("/api/v1/analytics/summary")
        assert summary_resp.status_code == 200
        assert summary_resp.json()["recent_transactions_count"] == 13


@pytest.mark.asyncio
async def test_tier4_scenario_recurring_monthly_statement_reconciliation():
    """Scenario 3: Monthly accounting workflow: upload Month 1, generate forecast, upload Month 2 with overlapping transactions, refit forecast."""
    # Month 1 Statement (January)
    m1_rows = [
        ["Date", "Description", "Debit", "Credit", "Balance"],
        ["2024-01-05", "Office Depot Supplies", "120.00", "", "5000.00"],
        ["2024-01-10", "Amazon Web Services", "340.50", "", "4659.50"],
        ["2024-01-15", "Client Retainer Payment", "", "4000.00", "8659.50"],
        ["2024-01-20", "Google Workspace", "72.00", "", "8587.50"],
        ["2024-01-28", "WeWork Office Rent", "1100.00", "", "7487.50"],
    ]
    # Month 2 Statement (February, with overlapping Jan 28 transaction)
    m2_rows = [
        ["Date", "Description", "Debit", "Credit", "Balance"],
        ["2024-01-28", "WeWork Office Rent", "1100.00", "", "7487.50"],  # Duplicate
        ["2024-02-05", "Office Depot Supplies", "85.00", "", "7402.50"],   # New
        ["2024-02-10", "Amazon Web Services", "390.00", "", "7012.50"],   # New
        ["2024-02-15", "Client Retainer Payment", "", "4000.00", "11012.50"],  # New
        ["2024-02-28", "WeWork Office Rent", "1100.00", "", "9912.50"],   # New
    ]

    pdf1 = generate_digital_pdf(m1_rows)
    pdf2 = generate_digital_pdf(m2_rows)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Month 1 upload
        r1 = await ac.post("/api/v1/statements/upload", files={"file": ("stmt_jan.pdf", pdf1, "application/pdf")})
        assert r1.status_code == 201
        assert r1.json()["newly_inserted"] == 5

        # Initial forecast
        f1 = await ac.post("/api/v1/forecasts/generate", json={"granularity": "DAILY", "horizon": 14})
        assert f1.status_code == 200

        # Month 2 upload with overlap
        r2 = await ac.post("/api/v1/statements/upload", files={"file": ("stmt_feb.pdf", pdf2, "application/pdf")})
        assert r2.status_code == 201
        assert r2.json()["newly_inserted"] == 4
        assert r2.json()["duplicates_skipped"] == 1

        # Total transactions should be 9
        txns_resp = await ac.get("/api/v1/transactions")
        assert txns_resp.json()["total"] == 9

        # Refit forecast with expanded history
        f2 = await ac.post("/api/v1/forecasts/generate", json={"granularity": "DAILY", "horizon": 14})
        assert f2.status_code == 200
        assert len(f2.json()["forecast_payload"]) == 14


@pytest.mark.asyncio
async def test_tier4_scenario_multimodal_digital_and_photo_consolidation():
    """Scenario 4: User consolidates online banking PDF statement and smartphone receipt/photo statement (PNG) into unified ledger."""
    digital_pdf = generate_digital_pdf()
    photo_png = get_scanned_image_bytes("PNG")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Ingest digital PDF
        r_pdf = await ac.post("/api/v1/statements/upload", files={"file": ("bank_estatement.pdf", digital_pdf, "application/pdf")})
        assert r_pdf.status_code == 201
        assert r_pdf.json()["newly_inserted"] == 6

        # Ingest photo PNG
        r_img = await ac.post("/api/v1/statements/upload", files={"file": ("receipt_scan.png", photo_png, "image/png")})
        assert r_img.status_code == 201
        assert r_img.json()["newly_inserted"] >= 10

        # Query combined ledger
        r_ledger = await ac.get("/api/v1/transactions?page_size=50")
        assert r_ledger.status_code == 200
        items = r_ledger.json()["items"]
        assert len(items) >= 16

        # Verify automated categorization applied across both sources
        categories = {t["category"] for t in items}
        assert len(categories) >= 2


@pytest.mark.asyncio
async def test_tier4_scenario_manual_bookkeeping_and_category_reassignment():
    """Scenario 5: User reviews uploaded statement, corrects multiple misclassified expenses, and confirms analytics category breakdown updates."""
    pdf_bytes = generate_digital_pdf()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Ingest statement
        await ac.post("/api/v1/statements/upload", files={"file": ("expenses.pdf", pdf_bytes, "application/pdf")})

        # List transactions
        txns_resp = await ac.get("/api/v1/transactions")
        items = txns_resp.json()["items"]
        assert len(items) >= 5

        # Reassign Uber to "Local Travel & Commute"
        uber = next(t for t in items if "Uber" in t["description"])
        p1 = await ac.patch(
            f"/api/v1/transactions/{uber['id']}/category",
            json={"category": "Local Travel & Commute"}
        )
        assert p1.status_code == 200
        assert p1.json()["category"] == "Local Travel & Commute"

        # Reassign Netflix to "Software Subscriptions"
        netflix = next(t for t in items if "Netflix" in t["description"])
        p2 = await ac.patch(
            f"/api/v1/transactions/{netflix['id']}/category",
            json={"category": "Software Subscriptions"}
        )
        assert p2.status_code == 200
        assert p2.json()["category"] == "Software Subscriptions"

        # Confirm analytics reflects reassignments
        summary_resp = await ac.get("/api/v1/analytics/summary")
        assert summary_resp.status_code == 200
        top_cats = [c["category"] for c in summary_resp.json()["top_categories"]]
        assert "Local Travel & Commute" in top_cats
        assert "Software Subscriptions" in top_cats
