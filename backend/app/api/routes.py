import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from sqlalchemy import delete, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import ForecastRun, Statement, Transaction
from app.schemas import (
    AnalyticsSummaryResponse,
    CategoryOverrideRequest,
    DeleteResponse,
    ForecastDataPoint,
    ForecastRequest,
    ForecastResponse,
    HistoricalDataPoint,
    ModelAccuracy,
    PaginatedTransactionsResponse,
    StatementRead,
    TopCategory,
    TransactionRead,
    UploadResponse,
)
from app.services.pdf_extractor import extract_tables_from_image, extract_tables_from_pdf
from app.services.sarima_engine import prepare_time_series, train_sarima_and_forecast

logger = logging.getLogger("routes")
router = APIRouter()


@router.post(
    "/statements/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload bank statement (PDF, JPG, PNG, WebP), extract tabular transactions, and bulk upsert"
)
async def upload_statement(
    file: UploadFile,
    db: AsyncSession = Depends(get_db)
):
    ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".webp"}
    file_ext = Path(file.filename or "").suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file format '{file_ext}'. Supported formats: PDF, JPG, JPEG, PNG, WebP."
        )

    try:
        content = await file.read()
    except Exception as ex:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read uploaded file: {ex}"
        )

    # 1. Create statement record in PROCESSING state
    statement = Statement(
        filename=file.filename,
        status="PROCESSING",
        total_debit=Decimal("0.00"),
        total_credit=Decimal("0.00"),
        row_count=0
    )
    db.add(statement)
    await db.commit()
    await db.refresh(statement)

    # 2. Run table extraction based on file format
    try:
        if file_ext == ".pdf":
            extracted_txns = extract_tables_from_pdf(content, filename=file.filename)
        else:
            extracted_txns = extract_tables_from_image(content, filename=file.filename)
    except Exception as ex:
        statement.status = "FAILED"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Statement table extraction failed: {ex}"
        )

    if not extracted_txns:
        statement.status = "COMPLETED"
        await db.commit()
        return UploadResponse(
            status="COMPLETED",
            statement=StatementRead.model_validate(statement),
            message="No tabular transactions were detected in the statement.",
            newly_inserted=0,
            duplicates_skipped=0,
            parsed_rows=[]
        )

    # 3. Deduplicate against existing row_hash records
    candidate_hashes = [t.row_hash for t in extracted_txns]
    existing_query = await db.execute(
        select(Transaction.row_hash).where(Transaction.row_hash.in_(candidate_hashes))
    )
    existing_hashes = set(existing_query.scalars().all())

    new_txns: List[Transaction] = []
    tot_debit = Decimal("0.00")
    tot_credit = Decimal("0.00")

    for t_dto in extracted_txns:
        if t_dto.row_hash in existing_hashes:
            continue

        txn_record = Transaction(
            statement_id=statement.id,
            txn_date=t_dto.txn_date,
            description=t_dto.description,
            amount=t_dto.amount,
            txn_type=t_dto.txn_type,
            category=t_dto.category,
            category_confidence=t_dto.category_confidence,
            category_source=t_dto.category_source,
            balance=t_dto.balance,
            row_hash=t_dto.row_hash,
        )
        new_txns.append(txn_record)
        existing_hashes.add(t_dto.row_hash)

        if t_dto.txn_type == "DEBIT":
            tot_debit += t_dto.amount
        else:
            tot_credit += t_dto.amount

    if new_txns:
        db.add_all(new_txns)

    # Update statement record
    statement.status = "COMPLETED"
    statement.total_debit = tot_debit
    statement.total_credit = tot_credit
    statement.row_count = len(new_txns)
    await db.commit()
    await db.refresh(statement)

    duplicates_skipped = len(extracted_txns) - len(new_txns)

    return UploadResponse(
        status="COMPLETED",
        statement=StatementRead.model_validate(statement),
        message=f"Successfully extracted {len(extracted_txns)} rows. Inserted {len(new_txns)} new records ({duplicates_skipped} duplicates skipped).",
        newly_inserted=len(new_txns),
        duplicates_skipped=duplicates_skipped,
        parsed_rows=extracted_txns
    )


@router.get(
    "/statements",
    response_model=List[StatementRead],
    summary="Get list of uploaded bank statements"
)
async def list_statements(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    query = select(Statement).order_by(Statement.uploaded_at.desc()).offset(offset).limit(limit)
    records = (await db.execute(query)).scalars().all()
    return [StatementRead.model_validate(r) for r in records]


@router.get(
    "/transactions",
    response_model=PaginatedTransactionsResponse,
    summary="Get paginated and filterable transaction records"
)
async def list_transactions(
    start_date: Optional[date] = Query(None, description="Filter transactions on or after this date"),
    end_date: Optional[date] = Query(None, description="Filter transactions on or before this date"),
    category: Optional[str] = Query(None, description="Filter by category"),
    txn_type: Optional[str] = Query(None, description="Filter by DEBIT or CREDIT"),
    search: Optional[str] = Query(None, description="Fuzzy search in description"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    query = select(Transaction)

    if start_date:
        query = query.where(Transaction.txn_date >= start_date)
    if end_date:
        query = query.where(Transaction.txn_date <= end_date)
    if category and category.lower() != "all":
        query = query.where(Transaction.category == category)
    if txn_type and txn_type.upper() in ("DEBIT", "CREDIT"):
        query = query.where(Transaction.txn_type == txn_type.upper())
    if search:
        query = query.where(Transaction.description.ilike(f"%{search}%"))

    # Total count
    count_query = select(func.count()).select_from(query.subquery())
    total_count = (await db.execute(count_query)).scalar_one()

    # Paginated results
    query = query.order_by(Transaction.txn_date.desc(), Transaction.id.desc()).offset(offset).limit(limit)
    records = (await db.execute(query)).scalars().all()

    items = [TransactionRead.model_validate(r) for r in records]

    return PaginatedTransactionsResponse(
        total=total_count,
        limit=limit,
        offset=offset,
        items=items
    )


@router.patch(
    "/transactions/{transaction_id}/category",
    response_model=TransactionRead,
    summary="Update transaction category inline"
)
async def update_transaction_category(
    transaction_id: uuid.UUID,
    payload: CategoryOverrideRequest,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Transaction).where(Transaction.id == transaction_id))
    txn = result.scalar_one_or_none()
    if not txn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction with ID {transaction_id} not found."
        )

    txn.category = payload.category.strip()
    txn.category_source = "USER_OVERRIDE"
    txn.category_confidence = 1.0
    await db.commit()
    await db.refresh(txn)
    return TransactionRead.model_validate(txn)


@router.delete(
    "/transactions",
    response_model=DeleteResponse,
    summary="Delete all transactions"
)
async def delete_all_transactions(
    db: AsyncSession = Depends(get_db)
):
    count_res = await db.execute(select(func.count(Transaction.id)))
    total_count = count_res.scalar_one() or 0

    if total_count == 0:
        return DeleteResponse(
            success=True,
            deleted_count=0,
            message="No transactions to delete."
        )

    await db.execute(delete(Transaction))
    # Reset statements totals
    await db.execute(
        update(Statement).values(
            row_count=0,
            total_debit=Decimal("0.00"),
            total_credit=Decimal("0.00")
        )
    )
    # Also clear stale forecasts
    await db.execute(delete(ForecastRun))
    await db.commit()

    return DeleteResponse(
        success=True,
        deleted_count=total_count,
        message=f"Successfully deleted all {total_count} transactions and reset ledger."
    )


@router.delete(
    "/transactions/{transaction_id}",
    response_model=DeleteResponse,
    summary="Delete a single transaction by ID"
)
async def delete_transaction(
    transaction_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Transaction).where(Transaction.id == transaction_id))
    txn = result.scalar_one_or_none()
    if not txn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction with ID {transaction_id} not found."
        )

    statement_id = txn.statement_id
    txn_type = txn.txn_type
    txn_amount = txn.amount

    await db.delete(txn)

    # If linked to a statement, update statement aggregates
    if statement_id:
        st_res = await db.execute(select(Statement).where(Statement.id == statement_id))
        st = st_res.scalar_one_or_none()
        if st:
            st.row_count = max(0, st.row_count - 1)
            if txn_type == "DEBIT":
                st.total_debit = max(Decimal("0.00"), st.total_debit - txn_amount)
            elif txn_type == "CREDIT":
                st.total_credit = max(Decimal("0.00"), st.total_credit - txn_amount)

    await db.commit()
    return DeleteResponse(
        success=True,
        deleted_count=1,
        message=f"Transaction {transaction_id} deleted successfully."
    )



@router.post(
    "/forecasts/generate",
    response_model=ForecastResponse,
    summary="Run SARIMA forecasting pipeline and persist run"
)
async def generate_forecast(
    request: ForecastRequest,
    db: AsyncSession = Depends(get_db)
):
    # Query all DEBIT transactions
    query = select(Transaction).where(Transaction.txn_type == "DEBIT").order_by(Transaction.txn_date.asc())
    records = (await db.execute(query)).scalars().all()

    if not records:
        return ForecastResponse(
            forecast_id=None,
            created_at=datetime.now(timezone.utc),
            granularity=request.granularity,
            horizon_steps=request.horizon,
            sarima_order="None",
            historical_series=[],
            forecast_payload=[],
            fallback_used=False,
            aic=None,
            rmse=None,
            mae=None,
            model_notes="No DEBIT transactions found to generate a forecast.",
            status="EMPTY"
        )

    # 1. Prepare time series
    series = prepare_time_series(records, granularity=request.granularity)
    if series.empty:
        return ForecastResponse(
            forecast_id=None,
            created_at=datetime.now(timezone.utc),
            granularity=request.granularity,
            horizon_steps=request.horizon,
            sarima_order="None",
            historical_series=[],
            forecast_payload=[],
            fallback_used=False,
            aic=None,
            rmse=None,
            mae=None,
            model_notes="Insufficient non-zero debit data to generate a forecast.",
            status="EMPTY"
        )

    # 2. Train and forecast
    forecast_result = train_sarima_and_forecast(
        series=series,
        granularity=request.granularity,
        horizon=request.horizon
    )

    # Convert forecast payload to dicts for JSON storage
    payload_dicts = [dp.model_dump() for dp in forecast_result["forecast_payload"]]

    # 3. Store in forecast_runs table
    forecast_run = ForecastRun(
        granularity=request.granularity,
        horizon_steps=request.horizon,
        sarima_order=forecast_result["order"],
        aic=forecast_result["aic"],
        rmse=forecast_result["rmse"],
        forecast_payload=payload_dicts
    )
    db.add(forecast_run)
    await db.commit()
    await db.refresh(forecast_run)

    return ForecastResponse(
        forecast_id=forecast_run.id,
        created_at=forecast_run.created_at,
        granularity=forecast_run.granularity,
        horizon_steps=forecast_run.horizon_steps,
        sarima_order=forecast_run.sarima_order,
        aic=forecast_run.aic,
        rmse=forecast_run.rmse,
        mae=forecast_result.get("mae"),
        historical_series=forecast_result["historical_series"],
        forecast_payload=forecast_result["forecast_payload"],
        fallback_used=forecast_result.get("fallback_used", False),
        model_notes=forecast_result.get("model_notes"),
        status="COMPLETED"
    )


@router.get(
    "/forecasts/latest",
    response_model=ForecastResponse,
    summary="Fetch the latest forecast run or generate one on demand"
)
async def get_latest_forecast(
    granularity: str = Query("DAILY", regex="^(DAILY|WEEKLY)$"),
    horizon: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db)
):
    query = (
        select(ForecastRun)
        .where(ForecastRun.granularity == granularity)
        .order_by(ForecastRun.created_at.desc())
        .limit(1)
    )
    latest = (await db.execute(query)).scalar_one_or_none()

    if latest:
        # Check historical series reconstruction
        debits = (
            await db.execute(
                select(Transaction).where(Transaction.txn_type == "DEBIT").order_by(Transaction.txn_date.asc())
            )
        ).scalars().all()
        series = prepare_time_series(debits, granularity=granularity)
        hist_list = [
            HistoricalDataPoint(date=dt.strftime("%Y-%m-%d"), actual=round(float(val), 2))
            for dt, val in series.items()
        ]
        payload = [ForecastDataPoint(**item) for item in latest.forecast_payload]

        return ForecastResponse(
            forecast_id=latest.id,
            created_at=latest.created_at,
            granularity=latest.granularity,
            horizon_steps=latest.horizon_steps,
            sarima_order=latest.sarima_order,
            aic=latest.aic,
            rmse=latest.rmse,
            mae=None,
            historical_series=hist_list,
            forecast_payload=payload,
            fallback_used="Baseline" in latest.sarima_order or "ARIMA(1,1,1)" in latest.sarima_order,
            model_notes="Retrieved persisted SARIMA forecast run.",
            status="COMPLETED"
        )

    # Check if there are any debit transactions before attempting on-demand generation
    debit_count_res = await db.execute(
        select(func.count(Transaction.id)).where(Transaction.txn_type == "DEBIT")
    )
    debit_count = debit_count_res.scalar_one_or_none() or 0
    if debit_count == 0:
        return ForecastResponse(
            forecast_id=None,
            created_at=datetime.now(timezone.utc),
            granularity=granularity,
            horizon_steps=horizon,
            sarima_order="None",
            historical_series=[],
            forecast_payload=[],
            fallback_used=False,
            aic=None,
            rmse=None,
            mae=None,
            model_notes="No DEBIT transactions found to generate a forecast.",
            status="EMPTY"
        )

    # Have debit transactions, generate fresh forecast
    return await generate_forecast(ForecastRequest(granularity=granularity, horizon=horizon), db=db)


@router.get(
    "/analytics/summary",
    response_model=AnalyticsSummaryResponse,
    summary="Get top-level KPI metrics, burn rate, and projected spend"
)
async def get_analytics_summary(db: AsyncSession = Depends(get_db)):
    # 1. Total spend in historical 30 days based on max txn_date
    max_date_res = await db.execute(select(func.max(Transaction.txn_date)))
    max_date = max_date_res.scalar_one_or_none()

    if not max_date:
        return AnalyticsSummaryResponse(
            total_spend_historical_30d=0.0,
            sarima_projected_spend_next_30d=0.0,
            mom_spend_delta_percent=0.0,
            daily_avg_burn_rate=0.0,
            model_accuracy=ModelAccuracy(),
            top_categories=[],
            recent_transactions_count=0,
            total_credit_30d=0.0,
            total_debit_30d=0.0,
        )

    window_30d_start = max_date - timedelta(days=30)
    window_prev_30d_start = max_date - timedelta(days=60)

    # 30d DEBIT spend
    spend_30d_res = await db.execute(
        select(func.sum(Transaction.amount)).where(
            Transaction.txn_type == "DEBIT",
            Transaction.txn_date >= window_30d_start,
            Transaction.txn_date <= max_date,
            Transaction.category != "Transfers",
        )
    )
    historical_30d_spend = float(spend_30d_res.scalar_one_or_none() or 0.0)

    # Prev 30d DEBIT spend for MoM delta comparison
    prev_spend_res = await db.execute(
        select(func.sum(Transaction.amount)).where(
            Transaction.txn_type == "DEBIT",
            Transaction.txn_date >= window_prev_30d_start,
            Transaction.txn_date < window_30d_start,
            Transaction.category != "Transfers",
        )
    )
    prev_30d_spend = float(prev_spend_res.scalar_one_or_none() or 0.0)

    # Total 30d Credit & Debit
    credit_30d_res = await db.execute(
        select(func.sum(Transaction.amount)).where(
            Transaction.txn_type == "CREDIT",
            Transaction.txn_date >= window_30d_start,
            Transaction.txn_date <= max_date,
        )
    )
    total_credit_30d = float(credit_30d_res.scalar_one_or_none() or 0.0)

    debit_30d_res = await db.execute(
        select(func.sum(Transaction.amount)).where(
            Transaction.txn_type == "DEBIT",
            Transaction.txn_date >= window_30d_start,
            Transaction.txn_date <= max_date,
        )
    )
    total_debit_30d = float(debit_30d_res.scalar_one_or_none() or 0.0)

    # Total transactions in last 30d
    count_res = await db.execute(
        select(func.count(Transaction.id)).where(
            Transaction.txn_date >= window_30d_start,
            Transaction.txn_date <= max_date,
        )
    )
    recent_count = int(count_res.scalar_one_or_none() or 0)

    daily_burn_rate = round(historical_30d_spend / 30.0, 2)

    # Top categories in 30d
    cat_res = await db.execute(
        select(Transaction.category, func.sum(Transaction.amount).label("cat_total"))
        .where(
            Transaction.txn_type == "DEBIT",
            Transaction.txn_date >= window_30d_start,
            Transaction.txn_date <= max_date,
            Transaction.category != "Transfers",
        )
        .group_by(Transaction.category)
        .order_by(desc("cat_total"))
    )
    cat_rows = cat_res.all()
    top_categories = []
    for cat, amt in cat_rows:
        amount_flt = float(amt)
        pct = (amount_flt / historical_30d_spend * 100.0) if historical_30d_spend > 0 else 0.0
        top_categories.append(
            TopCategory(
                category=cat,
                total_amount=round(amount_flt, 2),
                percentage=round(pct, 1)
            )
        )

    # Get or generate SARIMA 30d projection
    forecast_run_res = await db.execute(
        select(ForecastRun)
        .where(ForecastRun.granularity == "DAILY")
        .order_by(ForecastRun.created_at.desc())
        .limit(1)
    )
    latest_run = forecast_run_res.scalar_one_or_none()

    projected_30d = 0.0
    model_acc = ModelAccuracy()

    if latest_run and latest_run.forecast_payload:
        first_30_pts = latest_run.forecast_payload[:30]
        projected_30d = sum(pt.get("predicted", 0.0) for pt in first_30_pts)
        model_acc = ModelAccuracy(
            rmse=latest_run.rmse,
            aic=latest_run.aic,
            sarima_order=latest_run.sarima_order
        )
    else:
        # Run a quick 30d forecast
        try:
            debits = (
                await db.execute(
                    select(Transaction).where(Transaction.txn_type == "DEBIT").order_by(Transaction.txn_date.asc())
                )
            ).scalars().all()
            if debits:
                series = prepare_time_series(debits, granularity="DAILY")
                f_res = train_sarima_and_forecast(series, granularity="DAILY", horizon=30)
                projected_30d = sum(dp.predicted for dp in f_res["forecast_payload"][:30])
                model_acc = ModelAccuracy(
                    rmse=f_res.get("rmse"),
                    aic=f_res.get("aic"),
                    sarima_order=f_res.get("order")
                )
        except Exception as ex:
            logger.warning(f"Could not compute initial projection: {ex}")
            projected_30d = historical_30d_spend

    # MoM delta between historical 30d and projected next 30d
    if historical_30d_spend > 0:
        mom_delta = ((projected_30d - historical_30d_spend) / historical_30d_spend) * 100.0
    elif prev_30d_spend > 0:
        mom_delta = ((historical_30d_spend - prev_30d_spend) / prev_30d_spend) * 100.0
    else:
        mom_delta = 0.0

    return AnalyticsSummaryResponse(
        total_spend_historical_30d=round(historical_30d_spend, 2),
        sarima_projected_spend_next_30d=round(projected_30d, 2),
        mom_spend_delta_percent=round(mom_delta, 1),
        daily_avg_burn_rate=daily_burn_rate,
        model_accuracy=model_acc,
        top_categories=top_categories,
        recent_transactions_count=recent_count,
        total_credit_30d=round(total_credit_30d, 2),
        total_debit_30d=round(total_debit_30d, 2),
    )
