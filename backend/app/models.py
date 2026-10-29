import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, List, Optional

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, Numeric, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db import Base


# Use JSONB if on postgres, fallback to JSON
JsonType = JSON().with_variant(JSONB, "postgresql")


class Statement(Base):
    __tablename__ = "statements"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), default="PROCESSING", nullable=False)
    total_debit: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    total_credit: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    transactions: Mapped[List["Transaction"]] = relationship(
        "Transaction",
        back_populates="statement",
        cascade="all, delete-orphan",
        order_by="Transaction.txn_date.desc()",
        lazy="selectin"
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    statement_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("statements.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    txn_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    txn_type: Mapped[str] = mapped_column(String(16), nullable=False)  # "DEBIT" or "CREDIT"
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="Other", index=True)
    category_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    category_source: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    balance: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    row_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)

    statement: Mapped[Optional["Statement"]] = relationship("Statement", back_populates="transactions")


class ForecastRun(Base):
    __tablename__ = "forecast_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    granularity: Mapped[str] = mapped_column(String(16), nullable=False)  # "DAILY" or "WEEKLY"
    horizon_steps: Mapped[int] = mapped_column(Integer, nullable=False)
    sarima_order: Mapped[str] = mapped_column(String(64), nullable=False)
    aic: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rmse: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    forecast_payload: Mapped[Any] = mapped_column(JsonType, nullable=False)
