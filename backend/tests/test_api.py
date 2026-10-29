import io
import pytest
from httpx import ASGITransport, AsyncClient
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import Base, get_db
from app.main import app


# Test async engine using in-memory SQLite
test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    echo=False,
    future=True,
)
TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def override_get_db():
    async with TestSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


import asyncio
import pytest_asyncio


@pytest_asyncio.fixture(autouse=True, loop_scope="function")
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


def generate_test_pdf() -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    elements.append(Paragraph("Account Activity", styles["Heading1"]))

    table_data = [
        ["Date", "Description", "Debit", "Credit", "Balance"],
        ["2024-01-05", "Starbucks Store #991", "6.50", "", "1200.00"],
        ["2024-01-06", "Whole Foods Market", "82.30", "", "1117.70"],
        ["2024-01-07", "Payroll Direct Deposit", "", "2500.00", "3617.70"],
        ["2024-01-08", "PG&E Electric Bill", "95.00", "", "3522.70"],
        ["2024-01-09", "Uber Trip to Downtown", "24.50", "", "3498.20"],
        ["2024-01-10", "Netflix Subscription", "15.99", "", "3482.21"],
    ]
    t = Table(table_data)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(t)
    doc.build(elements)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_upload_and_transactions_flow():
    pdf_bytes = generate_test_pdf()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Upload statement PDF
        files = {"file": ("statement.pdf", pdf_bytes, "application/pdf")}
        upload_resp = await ac.post("/api/v1/statements/upload", files=files)
        assert upload_resp.status_code == 201
        upload_data = upload_resp.json()
        assert upload_data["status"] == "COMPLETED"
        assert upload_data["newly_inserted"] >= 5
        assert "parsed_rows" in upload_data
        assert len(upload_data["parsed_rows"]) >= 5

        # 2. Upload duplicate statement - should skip duplicates
        files_dup = {"file": ("statement_dup.pdf", pdf_bytes, "application/pdf")}
        upload_dup_resp = await ac.post("/api/v1/statements/upload", files=files_dup)
        assert upload_dup_resp.status_code == 201
        dup_data = upload_dup_resp.json()
        assert dup_data["newly_inserted"] == 0
        assert dup_data["duplicates_skipped"] >= 5

        # 3. List transactions
        txn_resp = await ac.get("/api/v1/transactions")
        assert txn_resp.status_code == 200
        txn_data = txn_resp.json()
        assert txn_data["total"] >= 5
        items = txn_data["items"]

        # Find Starbucks
        starbucks = next((x for x in items if "Starbucks" in x["description"]), None)
        assert starbucks is not None
        assert starbucks["category"] == "Food & Dining"

        # 4. Patch category inline
        txn_id = starbucks["id"]
        patch_resp = await ac.patch(
            f"/api/v1/transactions/{txn_id}/category",
            json={"category": "Coffee & Snacks"}
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["category"] == "Coffee & Snacks"

        # 5. Generate Forecast
        forecast_resp = await ac.post(
            "/api/v1/forecasts/generate",
            json={"granularity": "DAILY", "horizon": 14}
        )
        assert forecast_resp.status_code == 200
        f_data = forecast_resp.json()
        assert len(f_data["forecast_payload"]) == 14
        assert f_data["sarima_order"] is not None

        # 6. Fetch Latest Forecast
        latest_f_resp = await ac.get("/api/v1/forecasts/latest?granularity=DAILY&horizon=14")
        assert latest_f_resp.status_code == 200
        assert latest_f_resp.json()["forecast_id"] == f_data["forecast_id"]

        # 7. Get Analytics Summary
        summary_resp = await ac.get("/api/v1/analytics/summary")
        assert summary_resp.status_code == 200
        summary_data = summary_resp.json()
        assert summary_data["total_spend_historical_30d"] > 0
        assert summary_data["daily_avg_burn_rate"] >= 0
        assert len(summary_data["top_categories"]) > 0

        # 8. List Statements
        stmt_resp = await ac.get("/api/v1/statements")
        assert stmt_resp.status_code == 200
        stmt_data = stmt_resp.json()
        assert len(stmt_data) >= 1
        assert stmt_data[0]["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_delete_transaction_and_delete_all_flow():
    import uuid
    pdf_bytes = generate_test_pdf()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Upload statement
        files = {"file": ("statement.pdf", pdf_bytes, "application/pdf")}
        upload_resp = await ac.post("/api/v1/statements/upload", files=files)
        assert upload_resp.status_code == 201

        # Check transactions
        txns_resp = await ac.get("/api/v1/transactions?limit=100")
        assert txns_resp.status_code == 200
        initial_items = txns_resp.json()["items"]
        initial_total = txns_resp.json()["total"]
        assert initial_total >= 5

        # 1. Delete single transaction
        target_id = initial_items[0]["id"]
        del_single_resp = await ac.delete(f"/api/v1/transactions/{target_id}")
        assert del_single_resp.status_code == 200
        del_single_data = del_single_resp.json()
        assert del_single_data["success"] is True
        assert del_single_data["deleted_count"] == 1

        # Verify transaction is gone
        after_del_resp = await ac.get("/api/v1/transactions?limit=100")
        after_del_items = after_del_resp.json()["items"]
        assert after_del_resp.json()["total"] == initial_total - 1
        assert not any(t["id"] == target_id for t in after_del_items)

        # 2. Deleting nonexistent transaction returns 404
        fake_id = str(uuid.uuid4())
        del_fake_resp = await ac.delete(f"/api/v1/transactions/{fake_id}")
        assert del_fake_resp.status_code == 404

        # 3. Delete all transactions
        del_all_resp = await ac.delete("/api/v1/transactions")
        assert del_all_resp.status_code == 200
        del_all_data = del_all_resp.json()
        assert del_all_data["success"] is True
        assert del_all_data["deleted_count"] == initial_total - 1

        # Verify empty
        empty_resp = await ac.get("/api/v1/transactions")
        assert empty_resp.status_code == 200
        assert empty_resp.json()["total"] == 0
        assert len(empty_resp.json()["items"]) == 0

        # 4. Deleting all when empty returns 200 with deleted_count = 0
        del_empty_resp = await ac.delete("/api/v1/transactions")
        assert del_empty_resp.status_code == 200
        assert del_empty_resp.json()["deleted_count"] == 0


