<div align="center">

# FLUXO

**Know your future spend.**

Deterministic bank statement table extraction, PostgreSQL ledger normalization, and SARIMA time-series predictive spending modeling with 90% confidence intervals.

[![Next.js 15](https://img.shields.io/badge/Next.js%2015-0A0A0A?style=for-the-badge&logo=next.js&logoColor=FDE047)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0A0A0A?style=for-the-badge&logo=fastapi&logoColor=FDE047)](https://fastapi.tiangolo.com/)
[![Python 3.11+](https://img.shields.io/badge/Python%203.11+-0A0A0A?style=for-the-badge&logo=python&logoColor=FDE047)](https://www.python.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-0A0A0A?style=for-the-badge&logo=typescript&logoColor=FDE047)](https://www.typescriptlang.org/)
[![Neon Postgres](https://img.shields.io/badge/Neon%20Postgres-0A0A0A?style=for-the-badge&logo=postgresql&logoColor=FDE047)](https://neon.tech/)
[![Modal](https://img.shields.io/badge/Modal-0A0A0A?style=for-the-badge&logo=modal&logoColor=FDE047)](https://modal.com/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind%20CSS-0A0A0A?style=for-the-badge&logo=tailwindcss&logoColor=FDE047)](https://tailwindcss.com/)
[![Statsmodels](https://img.shields.io/badge/Statsmodels-0A0A0A?style=for-the-badge&logo=scipy&logoColor=FDE047)](https://www.statsmodels.org/)

[Features](#features) • [Architecture](#architecture) • [Tech Stack](#tech-stack) • [Getting Started](#getting-started) • [API Reference](#api-reference) • [Forecasting Engine](#how-the-forecasting-works)

</div>

---

<!-- TODO: Add product demo video or live URL -->
<!-- Live Demo: https://your-demo-url.vercel.app -->

## Screenshots

<!-- TODO: Add high-resolution dashboard screenshot -->
<!-- ![Fluxo Executive Dashboard](docs/screenshots/dashboard.png) -->

<!-- TODO: Add forecast chart and confidence ribbon screenshot -->
<!-- ![Fluxo Forecast Studio](docs/screenshots/forecast.png) -->

---

**CAPABILITIES**
## Everything you need. Nothing you don't.

<table>
  <tr>
    <td width="50%">
      <h3>Deterministic PDF Extraction</h3>
      <p>Spawns an isolated JVM CLI process via <code>opendataloader-pdf</code> to parse multi-bank tabular layouts directly into structured data. No LLM hallucinations or dropped row transactions.</p>
    </td>
    <td width="50%">
      <h3>SARIMA Time-Series Modeling</h3>
      <p>Automated seasonal autoregressive integrated moving average pipeline with ADF stationarity testing and bounded stepwise AIC grid searches across <code>(p,d,q)(P,D,Q)s</code>.</p>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <h3>90% Confidence Ribbons</h3>
      <p>Visualizes future spending uncertainty as an expanding fan ribbon using Recharts <code>ComposedChart</code>, giving treasury managers statistically bounded projections.</p>
    </td>
    <td width="50%">
      <h3>Backtested Model Accuracy</h3>
      <p>Validates projections against out-of-sample holdout test sets, calculating exact Root Mean Squared Error (RMSE) and Mean Absolute Error (MAE) metrics.</p>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <h3>Smart Category Classification</h3>
      <p>Machine learning classification pipeline categorizes merchant records into standard expenditure buckets, with full inline override capabilities in the ledger.</p>
    </td>
    <td width="50%">
      <h3>SHA-256 Deduplication</h3>
      <p>Cryptographic row hashing on transaction date, description, amount, and balance ensures multi-month overlapping statement uploads never duplicate ledger entries.</p>
    </td>
  </tr>
</table>

---

**TOPOLOGY**
## Architecture

```mermaid
flowchart TD
    subgraph Client ["Client Layer (Vercel)"]
        UI["Next.js 15 App Router<br/>(Tailwind CSS + Recharts)"]
        Dropzone["React Dropzone<br/>(Direct Binary Ingestion)"]
    end

    subgraph Serverless ["Compute & API Layer (Modal)"]
        FastAPI["FastAPI ASGI App<br/>(min_containers=1, Debian Slim)"]
        JVM["opendataloader-pdf<br/>(OpenJDK 17 Isolated Process)"]
        Normalizer["Normalizer & ML Classifier<br/>(SHA-256 Deduplication)"]
        SARIMA["SARIMA Forecaster<br/>(statsmodels + scikit-learn)"]
    end

    subgraph Storage ["Database Layer (Neon)"]
        Postgres[("Serverless PostgreSQL<br/>(asyncpg + SQLAlchemy NullPool)")]
    end

    Dropzone -->|PDF / Image Upload| FastAPI
    FastAPI -->|Extract Tables| JVM
    JVM -->|JSON Tables| Normalizer
    Normalizer -->|Idempotent Upsert| Postgres
    FastAPI -->|Query Historical Debits| Postgres
    Postgres -->|Debit Time Series| SARIMA
    SARIMA -->|AIC Grid Search & 90% CI| FastAPI
    FastAPI -->|Forecast JSON Payload| UI
```

---

**SPECIFICATIONS**
## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Frontend** | Next.js 15 (React 19, TypeScript) | Server and client components, App Router, static route generation |
| **Styling** | Tailwind CSS | Hyper-Saturated Fluid design system, dark-mode glassmorphism |
| **Visualizations** | Recharts | Multi-layer `ComposedChart` with 90% parametric fan ribbons and area fills |
| **Backend Framework** | FastAPI (Python 3.11+) | Asynchronous ASGI API, Pydantic v2 schemas, automated OpenAPI docs |
| **Cloud Compute** | Modal | Serverless ASGI hosting (`@modal.asgi_app`) with warm starts (`min_containers=1`) |
| **Table Extraction** | `opendataloader-pdf` + OpenJDK 17 | Deterministic JVM-based PDF table extraction with OCR fallback |
| **Forecasting Engine** | `statsmodels`, `pandas`, `scikit-learn` | SARIMAX time-series grid search, ADF stationarity, winsorization, backtesting |
| **Database** | Neon Serverless PostgreSQL | Relational storage via `asyncpg` and SQLAlchemy 2.0 async ORM (`NullPool`) |

---

**SOURCE TREE**
## Directory Structure

```text
finwise-analyzer/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── routes.py         # REST endpoints for upload, ledger, forecasts, analytics
│   │   ├── services/
│   │   │   ├── pdf_extractor.py  # opendataloader-pdf wrapper & OCR fallback
│   │   │   ├── normalizer.py     # Date parsing, credit/debit normalization & ML classifier
│   │   │   └── sarima_engine.py  # Resampling, ADF test, SARIMAX grid search & backtest
│   │   ├── config.py             # Pydantic BaseSettings (DATABASE_URL, FRONTEND_URL)
│   │   ├── db.py                 # AsyncEngine (NullPool for Neon pooler) & session factory
│   │   ├── main.py               # FastAPI application, CORS middleware, lifespan warmup
│   │   ├── models.py             # SQLAlchemy 2.0 async models (Statement, Transaction, ForecastRun)
│   │   └── schemas.py            # Pydantic v2 validation DTOs
│   ├── tests/                    # Unit, coverage, adversarial & integration test suite
│   ├── modal_app.py              # Modal Image definition, ASGI container & worker tasks
│   └── requirements.txt          # Backend Python dependencies
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── analytics/        # Category share & cashflow velocity views
│   │   │   ├── forecast/         # SARIMA forecast studio & scenario stress simulator
│   │   │   ├── statements/       # Ingestion audit log & direct PDF dropzone
│   │   │   ├── transactions/     # Filterable, sortable transaction ledger
│   │   │   ├── globals.css       # Hyper-Saturated Fluid design tokens & glassmorphism
│   │   │   ├── layout.tsx        # Inter/Mono font definitions & metadata
│   │   │   └── page.tsx          # Executive dashboard & cyber-yellow hero
│   │   ├── components/
│   │   │   ├── ui/               # Reusable primitives (Button, GlassCard, Pill, Skeleton)
│   │   │   ├── Footer.tsx        # Charcoal footer with architecture specs
│   │   │   ├── ForecastChart.tsx # Recharts ComposedChart with 90% confidence ribbon
│   │   │   ├── Header.tsx        # Navigation header delegator
│   │   │   ├── KpiRibbon.tsx     # 4-metric glassmorphic KPI summary cards
│   │   │   ├── Navbar.tsx        # Sticky top bar with logo mark & live API status
│   │   │   ├── TransactionTable.tsx # Paginated ledger with inline category override
│   │   │   └── UploadModal.tsx   # React Dropzone modal with 4-stage pipeline stepper
│   │   └── lib/
│   │       ├── api.ts            # Typed async API client functions
│   │       └── types.ts          # TypeScript interfaces & DTO definitions
│   ├── package.json              # Frontend scripts & dependencies
│   └── tailwind.config.ts        # Custom cyber-yellow / onyx tokens & animations
└── README.md
```

---

**EXECUTION**
## Getting Started

### 1. Prerequisites

* **Python 3.11+**
* **Node.js 18+ & npm**
* **OpenJDK 17** (required locally for `opendataloader-pdf` JVM execution)

### 2. Backend Setup

```bash
# Navigate to repository root
cd /path/to/BankStatementAnalyzer

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install backend dependencies
pip install -r backend/requirements.txt

# Run test suite
pytest backend/tests/

# Start local FastAPI server (default: http://127.0.0.1:8000)
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 3. Frontend Setup

```bash
# In a separate terminal, navigate to frontend
cd frontend

# Install npm dependencies
npm install

# Start Next.js development server (default: http://localhost:3000)
npm run dev
```

Visit [http://localhost:3000](http://localhost:3000) in your browser.

---

**CONFIGURATION**
## Environment Variables

Fluxo works out of the box with local SQLite (`bank_analyzer.db`) for testing, or connects to Neon Serverless Postgres in production.

<details>
<summary><strong>View Environment Variables Reference</strong></summary>

### Backend (`backend/.env` or system environment)

| Variable | Description | Default / Example |
|---|---|---|
| `DATABASE_URL` | Database connection string. Automatically converts `postgres://` to `postgresql+asyncpg://` and strips incompatible query params. | `sqlite+aiosqlite:///./bank_analyzer.db`<br/>*(Neon: `postgresql+asyncpg://user:pass@ep-sample-pooler.region.neon.tech/neondb?ssl=require`)* |
| `FRONTEND_URL` | CORS allowed origin(s), comma-separated or `*`. | `http://localhost:3000` |
| `APP_ENV` | Environment state (`development`, `production`, `test`). | `development` |
| `API_PREFIX` | Base prefix for all API routes. | `/api/v1` |
| `DEFAULT_SARIMA_HORIZON` | Forward forecasting step horizon in days. | `30` |
| `CONFIDENCE_ALPHA` | Significance level for forecast confidence intervals (`0.10` = 90% CI). | `0.10` |
| `CATEGORY_MODEL_PATH` | Path to pre-trained ML classifier joblib artifact. | `backend/ml/artifacts/category_classifier.joblib` |

### Frontend (`frontend/.env.local`)

| Variable | Description | Default / Example |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | Base URL pointing to the FastAPI backend service. | `http://localhost:8000` |

</details>

---

**ENDPOINTS**
## API Reference

All application endpoints are prefixed with `/api/v1`. Interactive OpenAPI documentation is available locally at `http://127.0.0.1:8000/docs`.

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/statements/upload` | Ingests PDF/image statement, runs JVM table parser, standardizes amounts, and upserts rows with SHA-256 deduplication. |
| `GET` | `/api/v1/statements` | Retrieves list of processed statement documents and parsing receipts. |
| `GET` | `/api/v1/transactions` | Paginated, sortable, and filterable transaction ledger (`start_date`, `end_date`, `category`, `txn_type`, `search`). |
| `PATCH` | `/api/v1/transactions/{id}/category` | Overrides transaction category inline with manual audit tagging. |
| `DELETE` | `/api/v1/transactions/{id}` | Deletes a single transaction record and updates statement summary figures. |
| `DELETE` | `/api/v1/transactions` | Purges all transactions and resets statement aggregates. |
| `POST` | `/api/v1/forecasts/generate` | Executes bounded AIC grid search across $(p,d,q)(P,D,Q)_s$ parameters and commits forecast run. |
| `GET` | `/api/v1/forecasts/latest` | Retrieves latest cached forecast run or fits one on demand. |
| `GET` | `/api/v1/analytics/summary` | Aggregates 30d Historical Spend, Projected Next 30d Spend, MoM Delta, Daily Burn Rate, and Category shares. |
| `GET` | `/health` | Probes service status and database connectivity. |

---

**MATHEMATICS**
## How the Forecasting Works

The forecasting pipeline is engineered for intermittent and seasonal financial cashflows:

1. **Temporal Resampling & Zero-Padding**  
   DEBIT transactions are aggregated to uniform daily (`s=7`) or weekly (`s=4`) intervals. Non-spending days are zero-padded to maintain continuous chronological time structure.

2. **Outlier Winsorization**  
   Non-zero spending is evaluated using interquartile range (IQR) fences and 99th percentile caps. Isolated massive spikes (e.g. quarterly tuition or down payments) are winsorized to prevent inflation of rolling variance.

3. **Stationarity & Differencing Orders ($d, D$)**  
   An Augmented Dickey-Fuller (ADF) test evaluates the series for unit roots. If non-stationary ($p > 0.05$), first differencing ($d=1$) is applied. For series with at least two seasonal periods ($2s$), seasonal differencing ($D=1$) is verified.

4. **Bounded AIC Grid Search**  
   A constrained parameter grid evaluates candidates:
   $$\text{Non-seasonal: } p \in [0, 1, 2], \; d \in [0, 1], \; q \in [0, 1, 2]$$
   $$\text{Seasonal: } P \in [0, 1], \; D \in [0, 1], \; Q \in [0, 1], \; s \in [7 \text{ (Daily)} \mid 4 \text{ (Weekly)}]$$
   The model minimizing the Akaike Information Criterion ($\text{AIC}$) is chosen.

5. **Parametric Confidence Ribbons (90% CI)**  
   Forecast distributions are extracted at significance level $\alpha = 0.10$. Confidence bounds expand over the forecast horizon:
   $$\hat{y}_{t+h} \pm z_{0.95} \cdot \sigma_h$$
   Negative bounds are floored at zero to reflect financial debit constraints.

6. **Cold-Start Fallback Cascade**  
   If the series has fewer than 14 observations or the SARIMA numerical optimizer fails to converge, the engine executes a deterministic fallback cascade:
   $$\text{SARIMA} \longrightarrow \text{ARIMA}(1,1,1) \longrightarrow \text{Holt-Winters Exponential Smoothing} \longrightarrow \text{Empirical Mean}$$

7. **Out-of-Sample Holdout Backtesting**  
   Model quality is validated by withholding the final 14–30 days of observations. Out-of-sample predictions are scored against actuals using Root Mean Squared Error (RMSE) and Mean Absolute Error (MAE).

---

**PRODUCTION**
## Deployment

### Step 1: Neon Serverless PostgreSQL
1. Create a serverless database on [Neon](https://neon.tech).
2. Copy the **Pooled Connection String** (`-pooler` endpoint) from the console.
3. Ensure the connection URL begins with `postgresql+asyncpg://` and append `?ssl=require`.
4. Initialize the database schema:
```bash
export DATABASE_URL="postgresql+asyncpg://<USER>:<PASSWORD>@<NEON_POOLER_HOST>/<DB_NAME>?ssl=require"
python3 -c "import asyncio; from app.db import init_db; asyncio.run(init_db())"
```

### Step 2: Backend to Modal
1. Authenticate with the Modal CLI:
```bash
modal setup
```
2. Store your Neon connection URL as a Modal Secret:
```bash
modal secret create neon-db DATABASE_URL="postgresql+asyncpg://<USER>:<PASSWORD>@<NEON_POOLER_HOST>/<DB_NAME>?ssl=require"
```
3. Deploy the ASGI container:
```bash
modal deploy backend/modal_app.py
```
Modal outputs your live deployment endpoint (e.g. `https://<WORKSPACE>--finwise-analyzer-fastapi-app.modal.run`).

### Step 3: Frontend to Vercel
1. In your Vercel project settings, set:
   * `NEXT_PUBLIC_API_URL`: Your Modal live endpoint.
2. Deploy via Vercel CLI or Git push:
```bash
cd frontend
vercel deploy --prod
```

---

<div align="center">

Built with FastAPI, Modal, Neon, and Next.js.

<!-- TODO: Add license information if applicable (e.g. MIT, Apache 2.0) -->

</div>
