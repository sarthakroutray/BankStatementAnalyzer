from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TransactionBase(BaseModel):
    txn_date: date
    description: str
    amount: Decimal
    txn_type: Literal["DEBIT", "CREDIT"]
    category: str = "Other"
    category_confidence: Optional[float] = None
    category_source: Optional[str] = None
    balance: Optional[Decimal] = None


class TransactionCreate(TransactionBase):
    statement_id: Optional[UUID] = None
    row_hash: str


class TransactionRead(TransactionBase):
    id: UUID
    statement_id: Optional[UUID] = None
    row_hash: str

    model_config = ConfigDict(from_attributes=True)


TransactionResponse = TransactionRead


class StatementBase(BaseModel):
    filename: str
    status: str = "PROCESSING"
    total_debit: Decimal = Decimal("0.00")
    total_credit: Decimal = Decimal("0.00")
    row_count: int = 0


class StatementRead(StatementBase):
    id: UUID
    uploaded_at: datetime
    transactions: Optional[List[TransactionRead]] = None

    model_config = ConfigDict(from_attributes=True)


class UploadResponse(BaseModel):
    status: str
    statement: StatementRead
    message: str
    newly_inserted: int
    duplicates_skipped: int
    parsed_rows: List[TransactionCreate] = Field(default_factory=list)


class ForecastRequest(BaseModel):
    granularity: Literal["DAILY", "WEEKLY"] = "DAILY"
    horizon: int = Field(default=30, ge=1, le=365)


class ForecastDataPoint(BaseModel):
    date: str
    predicted: float
    lower_ci: float
    upper_ci: float
    actual: Optional[float] = None


class HistoricalDataPoint(BaseModel):
    date: str
    actual: float


class ForecastResponse(BaseModel):
    forecast_id: Optional[Union[UUID, int, str]] = None
    created_at: Optional[Union[datetime, str]] = Field(default_factory=lambda: datetime.now(timezone.utc))
    granularity: str = "DAILY"
    horizon_steps: int = 30
    sarima_order: Optional[str] = "None"
    aic: Optional[float] = None
    rmse: Optional[float] = None
    mae: Optional[float] = None
    historical_series: List[Union[HistoricalDataPoint, Dict[str, Any]]] = Field(default_factory=list)
    forecast_payload: List[Union[ForecastDataPoint, Dict[str, Any]]] = Field(default_factory=list)
    fallback_used: bool = False
    model_notes: Optional[str] = None
    status: Optional[str] = "COMPLETED"

    model_config = ConfigDict(from_attributes=True)


class TopCategory(BaseModel):
    category: str
    total_amount: float
    percentage: float


class ModelAccuracy(BaseModel):
    rmse: Optional[float] = None
    aic: Optional[float] = None
    sarima_order: Optional[str] = None


class AnalyticsSummaryResponse(BaseModel):
    total_spend_historical_30d: float
    sarima_projected_spend_next_30d: float
    mom_spend_delta_percent: float
    daily_avg_burn_rate: float
    model_accuracy: ModelAccuracy
    top_categories: List[TopCategory]
    recent_transactions_count: int
    total_credit_30d: float
    total_debit_30d: float


class PaginatedTransactionsResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[TransactionRead]


class CategoryOverrideRequest(BaseModel):
    category: str


class DeleteResponse(BaseModel):
    success: bool = True
    deleted_count: int
    message: str

