import sys
from pathlib import Path
import modal

# Ensure backend directory is in sys.path so 'app' package resolves cleanly regardless of CWD
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Ensure artifacts directory exists locally before image definition
artifacts_local_path = (
    Path("backend/ml/artifacts")
    if Path("backend/ml/artifacts").exists()
    else backend_dir / "ml" / "artifacts"
)
artifacts_local_path.mkdir(parents=True, exist_ok=True)

# 1. Define Modal Container Image with Debian Slim, OpenJDK 17, and dependencies
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("openjdk-17-jre-headless", "procps")
    .pip_install(
        "fastapi[standard]",
        "sqlalchemy[asyncio]",
        "asyncpg",
        "aiosqlite",
        "pydantic-settings",
        "opendataloader-pdf>=2.5.0",
        "pandas",
        "numpy",
        "statsmodels",
        "scikit-learn==1.6.1",
        "joblib==1.4.2",
        "python-multipart",
        "reportlab",
        "pypdf",
        "python-dateutil",
    )
    .add_local_dir(
        str(artifacts_local_path),
        remote_path="/root/ml/artifacts"
    )
    .env({"CATEGORY_MODEL_PATH": "/root/ml/artifacts/category_classifier.joblib"})
    .add_local_python_source("app")
    .add_local_python_source("ml")
)

app = modal.App("finwise-analyzer", image=image)

# Modal secret for Neon Serverless Postgres
neon_secret = modal.Secret.from_name("neon-db", required_keys=["DATABASE_URL"])


# 2. Modal ASGI App Entrypoint with warm container configuration
@app.function(
    image=image,
    secrets=[neon_secret],
    min_containers=1,
    timeout=300,
)
@modal.asgi_app()
def fastapi_app():
    from app.main import app as web_app
    return web_app


# 3. Offloaded Modal worker function for heavy batch PDF extraction
@app.function(
    image=image,
    secrets=[neon_secret],
    timeout=600,
)
def extract_pdf_background(pdf_bytes: bytes, filename: str):
    from app.services.pdf_extractor import extract_tables_from_pdf
    txns = extract_tables_from_pdf(pdf_bytes, filename=filename)
    return [t.model_dump() for t in txns]


# 4. Offloaded Modal worker function for heavy time-series SARIMA grid search
@app.function(
    image=image,
    secrets=[neon_secret],
    timeout=600,
)
def train_sarima_background(transactions: list, granularity: str = "DAILY", horizon: int = 30):
    from app.services.sarima_engine import prepare_time_series, train_sarima_and_forecast
    series = prepare_time_series(transactions, granularity=granularity)
    result = train_sarima_and_forecast(series, granularity=granularity, horizon=horizon)
    return result
