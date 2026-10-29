import io
import uuid
import asyncio
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional

import numpy as np
import pandas as pd
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
from app.schemas import TransactionCreate
from app.services.pdf_extractor import (
    extract_raw_records_from_image_array,
    extract_tables_from_image,
    extract_transactions_from_images,
    is_amount,
    parse_amt,
    repair_balance,
    repair_date_str,
)
from app.services.sarima_engine import (
    _run_cold_start_fallback,
    determine_stationarity_orders,
    prepare_time_series,
    train_sarima_and_forecast,
    winsorize_series,
)


# Isolated in-memory SQLite database for adversarial tests
adv_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    echo=False,
    future=True,
)
AdvSessionLocal = async_sessionmaker(
    bind=adv_engine,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def override_adv_get_db():
    async with AdvSessionLocal() as session:
        yield session


@pytest_asyncio.fixture(autouse=True)
async def setup_adv_db():
    prev_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_adv_get_db
    async with adv_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with adv_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    if prev_override is not None:
        app.dependency_overrides[get_db] = prev_override
    else:
        app.dependency_overrides.pop(get_db, None)


# ===========================================================================
# 1. Date Parsing & Regex White-Box Adversarial Tests
# ===========================================================================

def test_adversarial_date_formats_and_separators():
    """Verify single-digit days/months, dot/slash/hyphen separators, ISO dates, and 2-digit years."""
    # Dot separators
    assert repair_date_str("2024.01.15") == "2024-01-15"
    assert repair_date_str("15.01.2024") == "15/01/2024"
    assert repair_date_str("2004/2019") == "20/04/2019"
    assert repair_date_str("2004-2019") == "20/04/2019"

    # Single-digit month/day with hyphens / slashes / dots
    # Mock image items to test extract_raw_records_from_image_array date parsing logic
    from app.services.pdf_extractor import extract_raw_records_from_image_array
    
    # Test internal date parsing behavior with synthetic OCR boxes
    # 1. Day-first statement with single-digit day: '1-4-2019'
    test_boxes = [
        # Line 1: Date, Desc, Amt, Bal
        ([[10, 10], [100, 10], [100, 25], [10, 25]], "1-4-2019", 0.99),
        ([[110, 10], [300, 10], [300, 25], [110, 25]], "Coffee Shop", 0.99),
        ([[310, 10], [380, 10], [380, 25], [310, 25]], "15.00", 0.99),
        ([[390, 10], [460, 10], [460, 25], [390, 25]], "985.00", 0.99),
        # Line 2: Single-digit month: '25/5/2019'
        ([[10, 35], [100, 35], [100, 50], [10, 50]], "25/5/2019", 0.99),
        ([[110, 35], [300, 35], [300, 50], [110, 50]], "Grocery Store", 0.99),
        ([[310, 35], [380, 35], [380, 50], [310, 50]], "50.00", 0.99),
        ([[390, 35], [460, 35], [460, 50], [390, 50]], "935.00", 0.99),
        # Line 3: ISO date with dots: '2024.01.15'
        ([[10, 60], [100, 60], [100, 75], [10, 75]], "2024.01.15", 0.99),
        ([[110, 60], [300, 60], [300, 75], [110, 75]], "Online Service", 0.99),
        ([[310, 60], [380, 60], [380, 75], [310, 75]], "20.00", 0.99),
        ([[390, 60], [460, 60], [460, 75], [390, 75]], "915.00", 0.99),
        # Line 4: 2-digit year: '15/02/24'
        ([[10, 85], [100, 85], [100, 100], [10, 100]], "15/02/24", 0.99),
        ([[110, 85], [300, 85], [300, 100], [110, 100]], "Monthly Gym", 0.99),
        ([[310, 85], [380, 85], [380, 100], [310, 100]], "30.00", 0.99),
        ([[390, 85], [460, 85], [460, 100], [390, 100]], "885.00", 0.99),
    ]

    # Mock get_ocr_engine to return synthetic boxes
    class MockOCR:
        def __call__(self, img):
            return test_boxes, 0.0

    import app.services.pdf_extractor as pe
    orig_get_ocr = pe.get_ocr_engine
    pe.get_ocr_engine = lambda: MockOCR()
    try:
        dummy_img = np.zeros((150, 500, 3), dtype=np.uint8)
        records, running_bal = extract_raw_records_from_image_array(dummy_img, running_balance=Decimal("1000.00"))
        assert len(records) == 4
        assert records[0]["txn_date"] == date(2019, 4, 1)
        assert records[1]["txn_date"] == date(2019, 5, 25)
        assert records[2]["txn_date"] == date(2024, 1, 15)
        assert records[3]["txn_date"] == date(2024, 2, 15)
        assert running_bal == Decimal("885.00")
    finally:
        pe.get_ocr_engine = orig_get_ocr


def test_adversarial_month_first_date_detection():
    """Verify month-first format (e.g. US format 04/25/2019) where second component > 12."""
    test_boxes = [
        # Line 1: US date: month=4, day=25 -> 25 > 12 triggers dayfirst = False
        ([[10, 10], [100, 10], [100, 25], [10, 25]], "04/25/2019", 0.99),
        ([[110, 10], [300, 10], [300, 25], [110, 25]], "US Vendor", 0.99),
        ([[310, 10], [380, 10], [380, 25], [310, 25]], "100.00", 0.99),
        ([[390, 10], [460, 10], [460, 25], [390, 25]], "900.00", 0.99),
        # Line 2: US date: month=4, day=10 -> should parse as April 10, not Oct 4
        ([[10, 35], [100, 35], [100, 50], [10, 50]], "04/10/2019", 0.99),
        ([[110, 35], [300, 35], [300, 50], [110, 50]], "Second US Vendor", 0.99),
        ([[310, 35], [380, 35], [380, 50], [310, 50]], "50.00", 0.99),
        ([[390, 35], [460, 35], [460, 50], [390, 50]], "850.00", 0.99),
    ]

    class MockOCR:
        def __call__(self, img):
            return test_boxes, 0.0

    import app.services.pdf_extractor as pe
    orig_get_ocr = pe.get_ocr_engine
    pe.get_ocr_engine = lambda: MockOCR()
    try:
        dummy_img = np.zeros((100, 500, 3), dtype=np.uint8)
        records, _ = extract_raw_records_from_image_array(dummy_img, running_balance=Decimal("1000.00"))
        assert len(records) == 2
        # Month first: 04/25 -> April 25, 04/10 -> April 10
        assert records[0]["txn_date"] == date(2019, 4, 25)
        assert records[1]["txn_date"] == date(2019, 4, 10)
    finally:
        pe.get_ocr_engine = orig_get_ocr


def test_adversarial_invalid_date_graceful_handling():
    """Verify invalid day/month numbers like 99/99/2024 or 2024-99-99 do not crash parser."""
    test_boxes = [
        ([[10, 10], [100, 10], [100, 25], [10, 25]], "99/99/2024", 0.99),
        ([[110, 10], [300, 10], [300, 25], [110, 25]], "Invalid Line", 0.99),
        ([[310, 10], [380, 10], [380, 25], [310, 25]], "100.00", 0.99),
        ([[10, 35], [100, 35], [100, 50], [10, 50]], "2024-13-45", 0.99),
        ([[110, 35], [300, 35], [300, 50], [110, 50]], "Second Invalid Line", 0.99),
        ([[310, 35], [380, 35], [380, 50], [310, 50]], "100.00", 0.99),
    ]

    class MockOCR:
        def __call__(self, img):
            return test_boxes, 0.0

    import app.services.pdf_extractor as pe
    orig_get_ocr = pe.get_ocr_engine
    pe.get_ocr_engine = lambda: MockOCR()
    try:
        dummy_img = np.zeros((100, 500, 3), dtype=np.uint8)
        records, _ = extract_raw_records_from_image_array(dummy_img)
        assert len(records) == 0
    finally:
        pe.get_ocr_engine = orig_get_ocr


# ===========================================================================
# 2. Extreme Balance Deltas, Negative Numbers & Fallback Guardrails
# ===========================================================================

def test_adversarial_balance_repair_and_delta_inference():
    """Verify balance repair for decimal omission and huge balance deltas."""
    # repair_balance cases
    assert repair_balance(None, Decimal("100.00"), Decimal("10.00")) is None
    assert repair_balance(Decimal("90.00"), None, Decimal("10.00")) == Decimal("90.00")

    # Missing decimal point: 13937391 instead of 139373.91
    # prev_bal = 289373.91, amt = 150000.00 (debit), new bal should be 139373.91
    repaired = repair_balance(Decimal("13937391"), Decimal("289373.91"), Decimal("150000.00"))
    assert repaired == Decimal("139373.91")

    # Extreme balance deltas: 50 million transfer
    test_boxes = [
        # Line 1: Opening balance
        ([[10, 10], [200, 10], [200, 25], [10, 25]], "OPENING BALANCE", 0.99),
        ([[300, 10], [400, 10], [400, 25], [300, 25]], "100,000,000.00", 0.99),
        # Line 2: Huge debit
        ([[10, 35], [100, 35], [100, 50], [10, 50]], "2024-01-10", 0.99),
        ([[110, 35], [250, 35], [250, 50], [110, 50]], "Major Acquisition", 0.99),
        ([[260, 35], [350, 35], [350, 50], [260, 50]], "49,999,999.50", 0.99),
        ([[360, 35], [450, 35], [450, 50], [360, 50]], "50,000,000.50", 0.99),
        # Line 3: Huge credit
        ([[10, 60], [100, 60], [100, 75], [10, 75]], "2024-01-15", 0.99),
        ([[110, 60], [250, 60], [250, 75], [110, 75]], "Series B Funding", 0.99),
        ([[260, 60], [350, 60], [350, 75], [260, 75]], "75,000,000.00", 0.99),
        ([[360, 60], [450, 60], [450, 75], [360, 75]], "125,000,000.50", 0.99),
    ]

    class MockOCR:
        def __call__(self, img):
            return test_boxes, 0.0

    import app.services.pdf_extractor as pe
    orig_get_ocr = pe.get_ocr_engine
    pe.get_ocr_engine = lambda: MockOCR()
    try:
        dummy_img = np.zeros((100, 500, 3), dtype=np.uint8)
        records, final_bal = extract_raw_records_from_image_array(dummy_img)
        assert len(records) == 2
        assert records[0]["txn_type"] == "DEBIT"
        assert records[0]["amount"] == Decimal("49999999.50")
        assert records[1]["txn_type"] == "CREDIT"
        assert records[1]["amount"] == Decimal("75000000.00")
        assert final_bal == Decimal("125000000.50")
    finally:
        pe.get_ocr_engine = orig_get_ocr


def test_adversarial_single_amount_and_type_hint_guardrails():
    """Verify single amount column rows (no balance column) using type hints and description keywords."""
    test_boxes = [
        # Line 1: Type hint CR
        ([[10, 10], [100, 10], [100, 25], [10, 25]], "2024-01-05", 0.99),
        ([[110, 10], [250, 10], [250, 25], [110, 25]], "Vendor Refund", 0.99),
        ([[260, 10], [300, 10], [300, 25], [260, 25]], "CR", 0.99),
        ([[310, 10], [380, 10], [380, 25], [310, 25]], "45.00", 0.99),
        # Line 2: Type hint DR
        ([[10, 35], [100, 35], [100, 50], [10, 50]], "2024-01-06", 0.99),
        ([[110, 35], [250, 35], [250, 50], [110, 50]], "ATM Cash", 0.99),
        ([[260, 35], [300, 35], [300, 50], [260, 50]], "DR", 0.99),
        ([[310, 35], [380, 35], [380, 50], [310, 50]], "100.00", 0.99),
        # Line 3: Description keyword "Salary" without hints or balance
        ([[10, 60], [100, 60], [100, 75], [10, 75]], "2024-01-07", 0.99),
        ([[110, 60], [250, 60], [250, 75], [110, 75]], "Monthly Salary Direct Deposit", 0.99),
        ([[310, 60], [380, 60], [380, 75], [310, 75]], "4500.00", 0.99),
        # Line 4: General expense without hint
        ([[10, 85], [100, 85], [100, 100], [10, 100]], "2024-01-08", 0.99),
        ([[110, 85], [250, 85], [250, 100], [110, 100]], "Office Supplies Depot", 0.99),
        ([[310, 85], [380, 85], [380, 100], [310, 100]], "82.50", 0.99),
    ]

    class MockOCR:
        def __call__(self, img):
            return test_boxes, 0.0

    import app.services.pdf_extractor as pe
    orig_get_ocr = pe.get_ocr_engine
    pe.get_ocr_engine = lambda: MockOCR()
    try:
        dummy_img = np.zeros((120, 500, 3), dtype=np.uint8)
        records, _ = extract_raw_records_from_image_array(dummy_img, running_balance=None)
        assert len(records) == 4
        assert records[0]["txn_type"] == "CREDIT"
        assert records[0]["balance"] is None
        assert records[1]["txn_type"] == "DEBIT"
        assert records[2]["txn_type"] == "CREDIT"  # inferred from "salary" keyword
        assert records[3]["txn_type"] == "DEBIT"   # default expense
    finally:
        pe.get_ocr_engine = orig_get_ocr


# ===========================================================================
# 3. Non-Standard Image Aspect Ratios, Resolutions & Corrupt Bytes
# ===========================================================================

def test_adversarial_image_aspect_ratios_and_color_modes():
    """Verify non-standard aspect ratios (super wide, super tall, tiny) and color modes (RGBA, L, CMYK)."""
    # 1. Super wide image (3000 x 50)
    wide_img = Image.new("RGBA", (3000, 50), color=(255, 255, 255, 255))
    wide_bytes = io.BytesIO()
    wide_img.save(wide_bytes, format="PNG")
    txns_wide = extract_tables_from_image(wide_bytes.getvalue(), "wide.png")
    assert isinstance(txns_wide, list)

    # 2. Super tall image (50 x 3000)
    tall_img = Image.new("L", (50, 3000), color=255)
    tall_bytes = io.BytesIO()
    tall_img.save(tall_bytes, format="JPEG")
    txns_tall = extract_tables_from_image(tall_bytes.getvalue(), "tall.jpg")
    assert isinstance(txns_tall, list)

    # 3. Micro tiny image (10 x 10)
    tiny_img = Image.new("RGB", (10, 10), color=(200, 200, 200))
    tiny_bytes = io.BytesIO()
    tiny_img.save(tiny_bytes, format="WEBP")
    txns_tiny = extract_tables_from_image(tiny_bytes.getvalue(), "tiny.webp")
    assert isinstance(txns_tiny, list)

    # 4. Corrupt non-image bytes
    corrupt_bytes = b"NOT_A_VALID_IMAGE_HEADER_CORRUPTED_BYTES_1234567890"
    txns_corrupt = extract_tables_from_image(corrupt_bytes, "corrupt.png")
    assert txns_corrupt == []


@pytest.mark.asyncio
async def test_adversarial_image_upload_endpoints():
    """Test image upload endpoint with non-standard PNG and WebP files via API."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Upload RGBA PNG
        png_img = Image.new("RGBA", (400, 100), color=(255, 255, 255, 255))
        png_bytes = io.BytesIO()
        png_img.save(png_bytes, format="PNG")
        resp_png = await ac.post(
            "/api/v1/statements/upload",
            files={"file": ("test_rgba.png", png_bytes.getvalue(), "image/png")},
        )
        assert resp_png.status_code == 201
        data_png = resp_png.json()
        assert data_png["status"] == "COMPLETED"

        # Upload WebP
        webp_img = Image.new("RGB", (200, 200), color=(100, 150, 200))
        webp_bytes = io.BytesIO()
        webp_img.save(webp_bytes, format="WEBP")
        resp_webp = await ac.post(
            "/api/v1/statements/upload",
            files={"file": ("test_doc.webp", webp_bytes.getvalue(), "image/webp")},
        )
        assert resp_webp.status_code == 201
        data_webp = resp_webp.json()
        assert data_webp["status"] == "COMPLETED"

        # Upload unsupported extension (e.g. .exe)
        resp_bad = await ac.post(
            "/api/v1/statements/upload",
            files={"file": ("malicious.exe", b"binary content", "application/octet-stream")},
        )
        assert resp_bad.status_code == 400
        assert "Invalid file format" in resp_bad.json()["detail"]


# ===========================================================================
# 4. Forecaster Horizon Boundary & Extreme Range Testing
# ===========================================================================

@pytest.mark.asyncio
async def test_adversarial_forecaster_empty_db_all_horizons():
    """Verify forecasts on empty DB across varied horizons (1, 7, 30, 90, 180, 365)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        horizons = [1, 7, 30, 90, 180, 365]
        for h in horizons:
            # POST /generate
            gen_resp = await ac.post("/api/v1/forecasts/generate", json={"granularity": "DAILY", "horizon": h})
            assert gen_resp.status_code == 200
            data = gen_resp.json()
            assert data["status"] == "EMPTY"
            assert data["horizon_steps"] == h
            assert data["forecast_payload"] == []
            assert data["historical_series"] == []
            assert "No DEBIT transactions" in data["model_notes"]

            # GET /latest
            latest_resp = await ac.get(f"/api/v1/forecasts/latest?granularity=DAILY&horizon={h}")
            assert latest_resp.status_code == 200
            l_data = latest_resp.json()
            assert l_data["status"] == "EMPTY"
            assert l_data["horizon_steps"] == h
            assert l_data["forecast_payload"] == []


def test_adversarial_forecaster_sparse_and_extreme_horizons():
    """Stress-test SARIMA engine directly with varied horizons on sparse, short, and cyclic series."""
    # 1. Ultra sparse series (< 4 points)
    dates_sparse = pd.date_range("2024-01-01", periods=3, freq="D")
    s_sparse = pd.Series([20.0, 45.0, 30.0], index=dates_sparse)
    res_sparse = train_sarima_and_forecast(s_sparse, granularity="DAILY", horizon=90)
    assert res_sparse["fallback_used"] is True
    assert len(res_sparse["forecast_payload"]) == 90
    assert "Sparse" in res_sparse["model_notes"]

    # 2. Medium series (< 2*s = 14 points)
    dates_med = pd.date_range("2024-01-01", periods=10, freq="D")
    s_med = pd.Series([10.0, 20.0, 15.0, 30.0, 25.0, 40.0, 35.0, 50.0, 45.0, 60.0], index=dates_med)
    for h in [7, 30, 90, 180]:
        res_med = train_sarima_and_forecast(s_med, granularity="DAILY", horizon=h)
        assert res_med["fallback_used"] is True
        assert len(res_med["forecast_payload"]) == h
        for pt in res_med["forecast_payload"]:
            assert pt.predicted >= 0.0
            assert pt.lower_ci >= 0.0
            assert pt.upper_ci >= pt.predicted

    # 3. Populated series (60 points) with horizon 7, 30, 90
    dates_full = pd.date_range("2024-01-01", periods=60, freq="D")
    base_pattern = [25.0, 30.0, 28.0, 35.0, 80.0, 90.0, 40.0]
    vals = [base_pattern[i % 7] + 5.0 for i in range(60)]
    s_full = pd.Series(vals, index=dates_full)
    for h in [7, 30, 90]:
        res_full = train_sarima_and_forecast(s_full, granularity="DAILY", horizon=h)
        assert res_full["fallback_used"] is False
        assert len(res_full["forecast_payload"]) == h
        for pt in res_full["forecast_payload"]:
            assert pt.predicted >= 0.0
            assert pt.lower_ci >= 0.0
            assert pt.upper_ci >= pt.predicted

    # 4. Weekly granularity with horizons 4, 12, 52
    dates_weekly = pd.date_range("2024-01-01", periods=30, freq="W-MON")
    s_weekly = pd.Series([200.0 + (i % 4) * 50.0 for i in range(30)], index=dates_weekly)
    for h in [4, 12, 52]:
        res_w = train_sarima_and_forecast(s_weekly, granularity="WEEKLY", horizon=h)
        assert len(res_w["forecast_payload"]) == h


def test_adversarial_stationarity_orders_and_fallback_convergence():
    """Verify ADF stationarity orders and graceful fallback on non-converging models."""
    # Ultra short series < 10 points
    s_short = pd.Series([10.0, 20.0, 30.0], index=pd.date_range("2024-01-01", periods=3, freq="D"))
    d, D = determine_stationarity_orders(s_short, s=7)
    assert d == 1 and D == 0

    # Test direct _run_cold_start_fallback execution with synthetic inputs
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    s = pd.Series([10.0, 10.0, 10.0, 10.0, 10.0], index=dates)
    future = pd.date_range("2024-01-06", periods=7, freq="D")
    fb_res = _run_cold_start_fallback(
        series=s,
        future_dates=future,
        historical_series=[],
        horizon=7,
        alpha=0.10,
        reason="Forced test fallback.",
    )
    assert fb_res["fallback_used"] is True
    assert len(fb_res["forecast_payload"]) == 7


# ===========================================================================
# 5. Rapid Sequential API Calls & Concurrency
# ===========================================================================

def generate_adversarial_pdf(row_count: int = 10, offset_days: int = 0) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    elements.append(Paragraph("Adversarial Statement", styles["Heading1"]))

    base = date(2024, 1, 1) + timedelta(days=offset_days)
    table_data = [["Date", "Description", "Debit", "Credit", "Balance"]]
    bal = 10000.0
    for i in range(row_count):
        d_str = (base + timedelta(days=i)).strftime("%Y-%m-%d")
        amt = 15.0 + (i * 3.5)
        bal -= amt
        table_data.append([d_str, f"Vendor Transaction #{i}_{offset_days}", f"{amt:.2f}", "", f"{bal:.2f}"])

    t = Table(table_data)
    elements.append(t)
    doc.build(elements)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_adversarial_rapid_sequential_and_concurrent_api_calls():
    """Verify system stability under rapid sequential statement uploads and concurrent queries."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Rapid sequential uploads of 5 distinct statements
        pdf_batches = [generate_adversarial_pdf(row_count=5, offset_days=i * 6) for i in range(5)]
        for i, pdf_bytes in enumerate(pdf_batches):
            resp = await ac.post(
                "/api/v1/statements/upload",
                files={"file": (f"statement_{i}.pdf", pdf_bytes, "application/pdf")},
            )
            assert resp.status_code == 201
            assert resp.json()["newly_inserted"] == 5

        # 2. Rapid sequential queries to /api/v1/forecasts/latest
        for i in range(10):
            r = await ac.get(f"/api/v1/forecasts/latest?granularity=DAILY&horizon={14 + i}")
            assert r.status_code == 200
            assert r.json()["status"] == "COMPLETED"

        # Concurrency: 10 parallel queries to /api/v1/transactions
        async def fetch_txns(offset: int):
            return await ac.get(f"/api/v1/transactions?limit=5&offset={offset}")

        txns_tasks = [fetch_txns(i * 2) for i in range(10)]
        txns_results = await asyncio.gather(*txns_tasks)
        for r in txns_results:
            assert r.status_code == 200
            assert r.json()["total"] == 25

        # 3. Rapid sequential forecast generation calls

        for h in [7, 14, 21, 30, 60]:
            r = await ac.post("/api/v1/forecasts/generate", json={"granularity": "DAILY", "horizon": h})
            assert r.status_code == 200
            assert r.json()["status"] == "COMPLETED"
            assert r.json()["horizon_steps"] == h

        # 4. Filtering and pagination stress on /api/v1/transactions
        # Test boundary limit values: limit=1, limit=500, offset=0, offset=100
        t_resp1 = await ac.get("/api/v1/transactions?limit=1&offset=0")
        assert t_resp1.status_code == 200
        assert len(t_resp1.json()["items"]) == 1

        t_resp500 = await ac.get("/api/v1/transactions?limit=500&offset=0")
        assert t_resp500.status_code == 200
        assert t_resp500.json()["total"] == 25
        assert len(t_resp500.json()["items"]) == 25

        # Test date range and type filtering
        f_resp = await ac.get(
            "/api/v1/transactions?start_date=2024-01-01&end_date=2024-01-10&txn_type=DEBIT&search=Vendor"
        )
        assert f_resp.status_code == 200
        assert f_resp.json()["total"] > 0

        # 5. Patch transaction category override and verify invalid ID
        first_txn_id = t_resp500.json()["items"][0]["id"]
        patch_ok = await ac.patch(
            f"/api/v1/transactions/{first_txn_id}/category",
            json={"category": "Adversarial Category"},
        )
        assert patch_ok.status_code == 200
        assert patch_ok.json()["category"] == "Adversarial Category"

        bad_uuid = uuid.uuid4()
        patch_404 = await ac.patch(
            f"/api/v1/transactions/{bad_uuid}/category",
            json={"category": "Should Fail"},
        )
        assert patch_404.status_code == 404

        # 6. Analytics summary with populated data
        summary_resp = await ac.get("/api/v1/analytics/summary")
        assert summary_resp.status_code == 200
        s_data = summary_resp.json()
        assert s_data["total_spend_historical_30d"] > 0
        assert s_data["recent_transactions_count"] > 0


# ===========================================================================
# 6. Deep Corner Coverage Hardening: Fallback Cascades & Analytics Boundaries
# ===========================================================================

@pytest.mark.asyncio
async def test_adversarial_routes_category_filter_and_mom_zero_historical():
    """Verify category filtering on /transactions and MoM delta calculation when historical spend is 0."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Test category filtering
        # Insert a credit at today (max_date) and a debit 45 days ago (prev_30d window)
        today = date(2024, 3, 1)
        prev_date = today - timedelta(days=45)

        # Upload a custom statement to establish these records
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=letter)
        table_data = [
            ["Date", "Description", "Debit", "Credit", "Balance"],
            [prev_date.strftime("%Y-%m-%d"), "Starbucks Store #102", "120.00", "", "5000.00"],
            [today.strftime("%Y-%m-%d"), "Interest Income", "", "50.00", "5050.00"],
        ]
        t = Table(table_data)
        doc.build([Paragraph("MoM Test Statement", getSampleStyleSheet()["Heading1"]), t])

        up_resp = await ac.post(
            "/api/v1/statements/upload",
            files={"file": ("mom_test.pdf", buf.getvalue(), "application/pdf")},
        )
        assert up_resp.status_code == 201

        # Test category query filter (hits line 179)
        cat_resp = await ac.get("/api/v1/transactions?category=Food%20%26%20Dining")
        assert cat_resp.status_code == 200
        assert cat_resp.json()["total"] >= 1

        # Query analytics summary: historical_30d_spend == 0, prev_30d_spend == 120.0 (hits lines 539-540)
        sum_resp = await ac.get("/api/v1/analytics/summary")
        assert sum_resp.status_code == 200
        s_data = sum_resp.json()
        assert s_data["total_spend_historical_30d"] == 0.0
        # MoM delta is ((0 - 120) / 120) * 100 = -100.0%
        assert s_data["mom_spend_delta_percent"] == -100.0


def test_adversarial_sarima_fallback_cascade(monkeypatch):
    """Verify fallback cascade when ARIMA(1,1,1) fails, falling back to Holt-Winters and Baseline."""
    import statsmodels.tsa.arima.model as sm_arima
    from app.services.sarima_engine import _run_cold_start_fallback

    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    s = pd.Series([10.0, 15.0, 12.0, 18.0, 22.0, 19.0, 25.0, 28.0, 24.0, 30.0], index=dates)
    future = pd.date_range("2024-01-11", periods=7, freq="D")

    # 1. Force ARIMA fit failure to test Holt-Winters fallback (lines 152-176)
    def broken_arima_fit(*args, **kwargs):
        raise RuntimeError("Simulated ARIMA fit failure")

    monkeypatch.setattr(sm_arima.ARIMA, "fit", broken_arima_fit)
    res_hw = _run_cold_start_fallback(
        series=s,
        future_dates=future,
        historical_series=[],
        horizon=7,
        alpha=0.10,
        reason="Testing Holt-Winters fallback cascade.",
    )
    assert res_hw["fallback_used"] is True
    assert "HoltWinters" in res_hw["order"]
    assert len(res_hw["forecast_payload"]) == 7

    # 2. Force both ARIMA and Holt-Winters failure to test Baseline(Mean) (lines 177-199)
    import statsmodels.tsa.holtwinters as sm_hw

    def broken_hw_fit(*args, **kwargs):
        raise RuntimeError("Simulated Holt-Winters fit failure")

    monkeypatch.setattr(sm_hw.ExponentialSmoothing, "fit", broken_hw_fit)
    res_base = _run_cold_start_fallback(
        series=s,
        future_dates=future,
        historical_series=[],
        horizon=7,
        alpha=0.10,
        reason="Testing Baseline fallback cascade.",
    )
    assert res_base["fallback_used"] is True
    assert "Baseline(Mean)" in res_base["order"]
    assert len(res_base["forecast_payload"]) == 7


def test_adversarial_sarima_grid_search_non_convergence(monkeypatch):
    """Verify grid search fallback when no candidate SARIMA model converges (lines 291-300)."""
    import statsmodels.tsa.statespace.sarimax as sm_sarimax

    # Synthetic series that meets seasonal length requirement
    dates = pd.date_range("2024-01-01", periods=20, freq="D")
    s = pd.Series([20.0 + (i % 7) * 5.0 for i in range(20)], index=dates)

    # Force candidate models to fail fit
    def broken_sarimax_fit(*args, **kwargs):
        raise RuntimeError("Simulated SARIMAX grid search divergence")

    monkeypatch.setattr(sm_sarimax.SARIMAX, "fit", broken_sarimax_fit)
    res = train_sarima_and_forecast(s, granularity="DAILY", horizon=14)
    assert res["fallback_used"] is True
    assert "SARIMA grid search did not converge" in res["model_notes"]
