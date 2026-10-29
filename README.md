# FinWise Bank Statement Analyzer & SARIMA Spending Forecaster

A production-ready full-stack application that accepts PDF bank statements, extracts tabular transactions deterministically using `opendataloader-pdf`, stores normalized financial records in **Neon Serverless Postgres**, runs a **SARIMA (Seasonal AutoRegressive Integrated Moving Average)** time-series pipeline to forecast future spending with 90% confidence intervals, and visualizes historical spend vs. forecast ribbons in a modern **Next.js** dashboard deployed on **Vercel**, backed by a serverless **FastAPI** application running on **Modal**.

---

## Architecture & Topology

- **Frontend (Vercel):** Next.js 15 (App Router, TypeScript), Tailwind CSS, Recharts (ComposedChart fan ribbon), Lucide Icons, React Dropzone.
- **Backend & Compute (Modal):** FastAPI ASGI deployment (`@modal.asgi_app()`) running inside a Debian-slim container with OpenJDK 17 and `min_containers=1` for warm starts. Heavy operations are also available as background worker functions (`@app.function()`).
- **PDF Table Extraction:** `opendataloader-pdf` spawning an isolated JVM CLI process outputting structured JSON tables, with resilient column mapping heuristics for multi-bank header variations.
- **Time-Series Forecaster:** `statsmodels` (`SARIMAX`), `pandas`, `numpy`, `scikit-learn`. Includes ADF stationarity testing, bounded AIC grid search over $(p,d,q)(P,D,Q,s)$, outlier winsorization, cold-start fallback (ARIMA/Holt-Winters), and out-of-sample holdout backtesting (RMSE/MAE).
- **Database (Neon):** Serverless PostgreSQL via `asyncpg` + `SQLAlchemy 2.0` async ORM configured with `NullPool` (PgBouncer connection pooling) and SHA-256 idempotency deduplication.

---

## Directory Structure

```text
finwise-analyzer/
├── backend/
│   ├── modal_app.py              # Modal Image definition, ASGI entrypoint & worker functions
│   ├── app/
│   │   ├── main.py               # FastAPI app, CORS, router registration
│   │   ├── config.py             # Pydantic BaseSettings (DATABASE_URL, FRONTEND_URL)
│   │   ├── db.py                 # AsyncEngine (with NullPool for Neon pooler) & session maker
│   │   ├── models.py             # SQLAlchemy 2.0 ORM models (Statement, Transaction, ForecastRun)
│   │   ├── schemas.py            # Pydantic v2 request/response DTOs
│   │   ├── services/
│   │   │   ├── pdf_extractor.py  # opendataloader-pdf wrapper & heuristic table parser
│   │   │   ├── normalizer.py     # Date parsing, debit/credit normalization, category tagging
│   │   │   └── sarima_engine.py  # Resampling, ADF stationarity, SARIMAX grid search & forecast
│   │   └── api/
│   │       └── routes.py         # REST endpoints for upload, transactions, and forecasts
│   ├── tests/                    # Comprehensive unit & integration test suite
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/                  # Next.js App Router (layout, page, globals.css)
│   │   ├── components/           # UploadModal, TransactionTable, ForecastChart, KpiRibbon, Header
│   │   └── lib/                  # Typed API client & data interfaces
│   ├── package.json
│   └── tailwind.config.ts
└── README.md
```

---

## Quickstart & Local Development

### 1. Prerequisites
- Python 3.11+
- Node.js 18+ & npm
- OpenJDK 17 (for local `opendataloader-pdf` JVM execution)

### 2. Backend Setup
```bash
# Navigate to repository root
cd /mnt/data/Projects/BankStatementAnalyzer

# Create virtual environment & install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

# Run backend test suite
PYTHONPATH=backend pytest backend/tests/

# Start local FastAPI development server
PYTHONPATH=backend uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Frontend Setup
```bash
cd frontend
npm install

# Start local Next.js development server (points to http://localhost:8000 by default)
npm run dev
```

Visit [http://localhost:3000](http://localhost:3000) to view the dashboard.

---

## Deployment Guide

### Step 1: Initialize Neon Serverless PostgreSQL
1. Create a serverless Postgres database on [Neon](https://neon.tech).
2. Copy the **Pooled Connection String** (`-pooler` hostname) from the Neon Console.
3. Make sure the scheme begins with `postgresql://` or `postgresql+asyncpg://` (e.g. `postgresql://user:password@ep-sample-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require`).
4. To initialize tables directly from your terminal:
```bash
export DATABASE_URL="postgresql+asyncpg://<USER>:<PASSWORD>@<NEON_POOLER_HOST>/<DB_NAME>?ssl=require"
python3 -c "import asyncio; from app.db import init_db; asyncio.run(init_db())"
```

### Step 2: Deploy Backend to Modal
1. Authenticate with Modal:
```bash
modal setup
```
2. Store your Neon connection URL as a Modal Secret:
```bash
modal secret create neon-db DATABASE_URL="postgresql+asyncpg://<USER>:<PASSWORD>@<NEON_POOLER_HOST>/<DB_NAME>?ssl=require"
```
3. Deploy the FastAPI ASGI application to Modal:
```bash
modal deploy backend/modal_app.py
```
Modal will output your live deployment URL (e.g., `https://<YOUR_MODAL_USERNAME>--finwise-analyzer-fastapi-app.modal.run`).

### Step 3: Deploy Frontend to Vercel
1. Set the environment variable in your Vercel project settings:
   - `NEXT_PUBLIC_API_URL`: Your Modal live deployment URL (e.g., `https://<YOUR_MODAL_USERNAME>--finwise-analyzer-fastapi-app.modal.run`).
2. Deploy via Vercel CLI or Git push:
```bash
cd frontend
vercel deploy --prod
```
The frontend sends PDF uploads directly to the Modal backend endpoint, bypassing Vercel's 4.5 MB payload cap and serverless execution timeouts during SARIMA grid searches.

---

## API Endpoints Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/statements/upload` | Upload PDF statement, execute JVM table extraction, normalize, and upsert |
| `GET` | `/api/v1/transactions` | Paginated and filterable transaction ledger (`start_date`, `end_date`, `category`, `txn_type`, `search`) |
| `PATCH` | `/api/v1/transactions/{id}/category` | Override transaction category inline |
| `POST` | `/api/v1/forecasts/generate` | Run bounded SARIMA grid search over $(p,d,q)(P,D,Q,s)$ and store forecast run |
| `GET` | `/api/v1/forecasts/latest` | Retrieve latest cached forecast run or fit on demand |
| `GET` | `/api/v1/analytics/summary` | Top KPI metrics: Historical 30d Spend, Projected Next 30d Spend, Burn Rate, Model Accuracy, Top Categories |
| `GET` | `/health` | Health check probe |
